"""
app.py - Flask-based server.

Copyright (c) 2019 by Thomas J. Daley, J.D.
"""
__author__ = "Thomas J. Daley, J.D."
__version__ = "0.0.1"

import argparse
import random
from flask import Flask, render_template, request, flash, redirect, url_for, session, logging, make_response, jsonify
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
from functools import wraps

from webservice import WebService
WEBSERVICE = None

from util.database import Database
DATABASE = Database()
DATABASE.connect()

app = Flask(__name__)

# Decorator to check if user is logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash("Unauthorized - Please Log In", "danger")
            return redirect(url_for("login"))
    return wrap

# Decorator to check if user is an administrator
def is_admin_user(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if session['is_admin']:
            return f(*args, **kwargs)
        else:
            flash("Unauthorized - Please Log In As An Administrator", "danger")
            return redirect(url_for("login"))
    return wrap

# Helper to create Public Data credentials from session variables
def pd_credentials(mysession)->dict:
    return {"username": session["pd_username"], "password": session["pd_password"]}

@app.route('/', methods=['GET'])
def index():
    return render_template('home.html')

@app.route('/about', methods=['GET'])
def about():
    return render_template('about.html')

def join_results(search_type:str, prior_results:dict, new_results:list)->dict:
    """
    Join the new results with the prior results disjunctively or conjunctively.

    Args:
        search_type (str): "disjunctive" (or the results) or "conjunctive" (and the results)
        prior_results (dict): results from prior searches. (key = db+ed+rec)
        new_results (list): results from latest search.
    
    Returns:
        (dict): joined results
    """
    # Disjunctive search means merge all the search results into a super-set
    # containing all results found in all searches.
    if search_type == "disjunctive":
        for result in new_results:
            key = "{}-{}-{}".format(result.db, result.ed, result.rec)
            prior_results[key] = result
        return prior_results

    # Conjunctive search means the end result must be just those results
    # that were in each sub search.

    # First, convert the array to a dictionary
    new_results_dict = {}
    for result in new_results:
        key = "{}-{}-{}".format(result.db, result.ed, result.rec)
        new_results_dict[key] = result

    # Now find the keys in common
    if prior_results:
        merged_result = {key:prior_results[key] for key in prior_results.keys() & new_results_dict.keys()}
    else:
        merged_result = new_results_dict
    return merged_result

def filter_results(results:list, case_id:str, category:str):
    excluded = DATABASE.get_case_items(session['email'], case_id, "X{}".format(category))
    if excluded:
        for item in results:
            if item.key() in excluded:
                item.case_status = "X"

    included = DATABASE.get_case_items(session['email'], case_id, category)
    if included:
        for item in results:
            if item.key() in included:
                item.case_status = "I"

def search_drivers(search_type, search_terms, search_state):
    (success, message, results) = WEBSERVICE.drivers_license(
        pd_credentials(session),
        search_terms=search_terms,
        search_scope=search_type,
        us_state=search_state)

    if success:
        if not results:
            message = """
            No drivers found that match ALL the search criteria. This can be for two reasons:
            (1) There really aren't any driverss that match the combined search criteria; or
            (2) The search criteria were too broad which resulted in the search results to be truncated thus
            reducing the number of drivers that matched all criteria. If you used a criterion in the "entire record"
            field that would return more than 1000 results, the second explanation probably applies.
            """
            flash(message, "warning")
            return redirect(url_for('search_dl'))
        
        flash("Found {} matching drivers.".format(len(results)), "success")
        return render_template('drivers.html', drivers=results)

    form = request.query()
    return render_template("search_error.html", formvariables=form, operation="Search: DL", message=message)

@app.route('/search/dl_address', methods=['GET'])
@is_logged_in
def search_dl_address():
    search_type = "main"
    search_terms = request.args.get('a')
    search_state = request.args.get('s').lower()
    return search_drivers(search_type, search_terms, search_state)

@app.route('/search/dl', methods=['GET', 'POST'])
@is_logged_in
def search_dl():
    if request.method == 'GET':
        return render_template('search_dl.html')

    form = request.form
    search_type = form["search_type"]
    search_terms = form["search_terms"]
    search_state = form["state"]
    return search_drivers(search_type, search_terms, search_state)

@app.route('/driver/<string:db>/<string:ed>/<string:rec>/<string:state>/', methods=['GET'])
@is_logged_in
def driver_details(db, ed, rec, state):
    (success, message, result) = WEBSERVICE.driver_details(pd_credentials(session), db, ed, rec, state)
    if success:
        return render_template('driver.html', driver=result)
    return render_template("search_error.html", formvariables=[], operation="Search: DL Details", message=message)

@app.route('/search/dmv', methods=['GET', 'POST'])
@is_logged_in
def search_dmv():
    if request.method == 'GET':
        return render_template('search_dmv.html')

    # Process each field specified by the user, either conjuncitively or disjunctively.
    form = request.form
    search_type = form["search_type"]
    net_results = {}

    if form["owner_name"]:
        (success, message, results) = WEBSERVICE.dmv_name(pd_credentials(session), search_terms=form['owner_name'], us_state=form['state'])
        print("Found {} records for {} search for '{}'.".format(len(results), "owner_name", form["owner_name"]))
        filter_results(results, form['case_id'], "PROPERTY:VEHICLE")
        net_results = join_results(search_type, net_results, results)

    if form["plate"]:
        (success, message, results) = WEBSERVICE.dmv_plate(pd_credentials(session), search_terms=form['plate'], us_state=form['state'])
        print("Found {} records for {} search for '{}'.".format(len(results), "plate", form["plate"]))
        filter_results(results, form['case_id'], "PROPERTY:VEHICLE")
        net_results = join_results(search_type, net_results, results)

    if form["vin"]:
        (success, message, results) = WEBSERVICE.dmv_vin(pd_credentials(session), search_terms=form['vin'], us_state=form['state'])
        print("Found {} records for {} search for '{}'.".format(len(results), "vin", form["vin"]))
        filter_results(results, form['case_id'], "PROPERTY:VEHICLE")
        net_results = join_results(search_type, net_results, results)

    if form["search"]:
        (success, message, results) = WEBSERVICE.dmv_any(pd_credentials(session), search_terms=form['search'], us_state=form['state'])
        print("Found {} records for {} search for '{}'.".format(len(results), "any", form["search"]))
        filter_results(results, form['case_id'], "PROPERTY:VEHICLE")
        net_results = join_results(search_type, net_results, results)

    if success:
        results = [net_results[key] for key in net_results.keys()]
        results = sorted(results, key = lambda i: (i.case_status, i.year_make_model))

        if not results:
            message = """
            No vehicles found that match ALL the search criteria. This can be for two reasons:
            (1) There really aren't any vehicles that match the combined search criteria; or
            (2) The search criteria were too broad which resulted in the search results to be truncated thus
            reducing the number of vehicles that matched all criteria. If you used a criterion in the "entire record"
            field that would return more than 1000 results, the second explanation probably applies.
            """
            flash(message, "warning")
            return redirect(url_for('search_dmv'))
        
        flash("Found {} matching vehicles.".format(len(results)), "success")
        return render_template('vehicles.html', vehicles=results)
    return render_template("search_error.html", formvariables=form, operation="Search: DMV", message=message)

@app.route('/vehicle/<string:db>/<string:ed>/<string:rec>/<string:state>/', methods=['GET'])
@is_logged_in
def vehicle_details(db, ed, rec, state):
    (success, message, result) = WEBSERVICE.dmv_details(pd_credentials(session), db, ed, rec, state)
    if success:
        return render_template('vehicle.html', vehicle=result)
    return render_template("search_error.html", formvariables=[], operation="Search: DMV Details", message=message)

@app.route('/search/rp', methods=['GET'])
@is_logged_in
def search_rp_get():
    return render_template('search_rp.html')

class AddCaseForm(Form):
    cause_number = StringField("Cause number", [validators.DataRequired(), validators.Length(min=1, max=50)])
    description = StringField("Description", [validators.DataRequired(), validators.Length(min=1, max=50)])
    us_state = StringField("State", [validators.Length(min=2, max=2)])
    county = StringField("County", [validators.Length(min=0, max=50)])
    case_type = StringField("Case type", [validators.Length(min=0, max=50)])
    created_by = StringField("Created by")
    time_str = StringField("Create date")

@app.route('/case/add/', methods=['GET', 'POST'])
@is_logged_in
def add_case():
    form = AddCaseForm(request.form)

    if request.method == 'POST' and form.validate():
        fields = request.form
        myfields = {key:value for (key, value) in fields.items()}
        myfields["email"] = session["email"]
        myfields["created_by"] = session["email"]
        success = DATABASE.add_case(myfields)
        if success:
            flash("Case {} added.".format(myfields["cause_number"]), 'success')
            return redirect(url_for('list_cases'))
        flash("Failed to add case. Check log for explanation.", "danger")
        return redirect(url_for("add_case"))

    return render_template('case.html', form=form)

@app.route('/case/<string:id>/', methods=['GET', 'POST'])
@is_logged_in
def get_case(id):
    if request.method == 'POST':
        fields = request.form
        myfields = {key:value for (key, value) in fields.items()}
        myfields['_id'] = id
        myfields['email'] = session['email']
        result = DATABASE.update_case(myfields)
        if result:
            return redirect(url_for('list_cases'))
        flash("Failed to update case. Check log for explanation.", "danger")
        return redirect(url_for('list_cases'))
    
    # Show the case on a GET request
    case = DATABASE.get_case({"_id": id, "email": session["email"]})
    myfields = {key:value for (key, value) in case.items()}
    form = AddCaseForm(**myfields)
    return render_template("case.html", form=form)

@app.route('/cases', methods=['GET'])
@is_logged_in
def list_cases():
    cases = DATABASE.get_cases({"email": session["email"]})
    return render_template('cases.html', cases=cases)

@app.route('/case/add_item/', methods=['POST'])
@is_logged_in
def add_case_item():
    fields = request.form
    item = {key:value for (key, value) in fields.items() if key not in ['case_id', 'category', 'key']}
    case_id = fields['case_id']
    category = fields['category']
    key = fields['key']
    # Add to the included list and remove from the excluded list.
    success = DATABASE.add_to_case(session['email'], case_id, category, key, item)
    success = DATABASE.del_from_case(session['email'], case_id, "X"+category, key, item)
    return jsonify({"success": success, "message": "Nothing to say."})

@app.route('/case/del_item/', methods=['POST'])
@is_logged_in
def del_case_item():
    fields = request.form
    item = {key:value for (key, value) in fields.items() if key not in ['case_id', 'category', 'key']}
    case_id = fields['case_id']
    category = fields['category']
    key = fields['key']
    # Remove from included list and add to excluded list.
    success = DATABASE.del_from_case(session['email'], case_id, category, key, item)
    success = DATABASE.add_to_case(session['email'], case_id, "X"+category, key, item)
    return jsonify({"success": success, "message": "Nothing to say."})

class RegisterForm(Form):
    name = StringField("Name", [validators.DataRequired(), validators.Length(min=1, max=50)])
    email = StringField("Email", [validators.Length(min=6, max=50)])
    password = PasswordField("Password", [
        validators.DataRequired(),
        validators.EqualTo('confirm', "Passwords do no match.")
        ])
    confirm = PasswordField("Confirm password")
    pd_username = StringField("Public Data username", validators=[validators.DataRequired()])
    pd_password = StringField("Public Data password", validators=[validators.DataRequired()])
    zillow_key = StringField("Zillow API key", validators=[validators.DataRequired()])

@app.route("/queries", methods=['GET'])
@is_logged_in
@is_admin_user
def list_query_cache():
    queries = DATABASE.get_query_cache(50)
    return render_template("queries.html", queries=queries)

@app.route("/query/<string:id>/", methods=['GET'])
@is_logged_in
@is_admin_user
def show_query(id):
    result = DATABASE.get_query_cache_item_result(id)
    return render_template("query_result.html", result=result)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)

    if request.method == 'POST' and form.validate():
        fields = request.form
        myfields = {key:value for (key, value) in fields.items()}
        myfields["password"] = sha256_crypt.hash(str(fields["password"]))
        del myfields["confirm"] # saving that to the db defeats the purpose of encryption
        success = DATABASE.add_user(myfields)
        if success:
            flash("Your registration has been saved--Please login.", 'success')
            return redirect(url_for('login'))

        flash("{} is already registered.".format(fields["email"]), 'danger')
        return redirect(url_for('register'))

    return render_template('register.html', form=form)

class SettingsForm(Form):
    name = StringField("Name", [validators.DataRequired(), validators.Length(min=1, max=50)])
    password = PasswordField("Current password", [
        validators.DataRequired()
        ])
    pd_username = StringField("Public Data username", validators=[validators.DataRequired()])
    pd_password = StringField("Public Data password", validators=[validators.DataRequired()])
    zillow_key = StringField("Zillow API key", validators=[validators.DataRequired()])

@app.route('/settings', methods=['GET', 'POST'])
@is_logged_in
def settings():
    myfields = {"email": session['email']}
    result = DATABASE.get_user(myfields)
    myfields = {key:value for (key, value) in result.items() if key != "password"}
    form = SettingsForm(**myfields)

    # Email not found - something fishy is going on.
    if not result:
        message = "Oddly, {} is not registered as a user.".format(myfields['email'])
        flash(message, "danger")
        return redirect(url_for("logout"))

    if request.method == 'POST':
        # Email found - do passwords match?
        password_candidate = request.form["password"]
        if sha256_crypt.verify(password_candidate, result["password"]):
            # Yes, passwords match
            messages = ["Your settings have been updated.", "Your settings are updated.", "Your changes have been saved."]
            message = random.choice(messages)
            fields = request.form
            myfields = {key:value for (key, value) in fields.items() if key != "password" and value}
            myfields['email'] = session['email']
            session['pd_username'] = myfields['pd_username']
            session['pd_password'] = myfields['pd_password']
            session['zillow_key'] = myfields['zillow_key']
            DATABASE.update_user(myfields)
            return render_template("home.html", msg=message)

    return render_template('settings.html', form=form, old_data=result)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        myfields = {"email": request.form['email']}
        result = DATABASE.get_user(myfields)
        print(result)

        # Email not found in the user's table
        if not result:
            message = "{} is not regsitered as a user.".format(myfields["email"])
            return render_template("login.html", error=message)

        # Email found - Do passwords match?
        password_candidate = request.form["password"]
        if sha256_crypt.verify(password_candidate, result["password"]):
            # Yes, passwords match
            messages = ["Welcome back, {}!!", "Good to see you again, {}!!", "Hey, {}, welcome back!!"]
            message = (random.choice(messages)).format(result["name"])
            session['logged_in'] = True
            session['email'] = result['email']
            session['pd_username'] = result['pd_username']
            session['pd_password'] = result['pd_password']
            session['zillow_key'] = result['zillow_key']
            session['is_admin'] = "admin" in result and result["admin"] == "Y"
            return render_template("home.html", msg=message)

        # No, passwords do not match
        messages = ["We don't recognize that email/password combination.", "Invalid email or password", "Email and password do not match"]
        message = random.choice(messages)
        return render_template("login.html", error=message)

    return render_template('login.html')

@app.route("/logout")
def logout():
    session.clear()
    messages = ["Good bye!!", "Hope to see you again soon.", "Thank you for visiting!!"]
    flash(random.choice(messages), "success")
    return redirect(url_for('login'))

if __name__ == "__main__":
    #global WEBSERVICE
    parser = argparse.ArgumentParser(description="Webservice for DiscoveryBot")
    parser.add_argument("--debug", help="Run server in debug mode", action='store_true')
    parser.add_argument("--port", help="TCP port to listen on", type=int, default=5001)
    parser.add_argument("--zillowid", "-z", help="Zillow API credential from https://www.zillow.com/howto/api/APIOverview.htm")
    args = parser.parse_args()

    WEBSERVICE = WebService(args.zillowid)
    app.secret_key="SDFIIUWER*HGjdf8*"
    app.run(debug=args.debug, port=args.port)