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

from functools import wraps

from views.decorators import is_admin_user, is_logged_in, is_case_set

from webservice import WebService
WEBSERVICE = None

from util.database import Database
DATABASE = Database()
DATABASE.connect()

app = Flask(__name__)

# Helper to create Public Data credentials from session variables
def pd_credentials(mysession)->dict:
    return {"username": session["pd_username"], "password": session["pd_password"]}

# Load routes defined in the views folder
from views.login.login import login
app.register_blueprint(login)

from views.info.info_routes import info_routes
app.register_blueprint(info_routes)

from views.cases.case_routes import case_routes
app.register_blueprint(case_routes)

from views.admin.admin_routes import admin_routes
app.register_blueprint(admin_routes)

print(app.url_map)

@app.route('/', methods=['GET'])
def index():
    return render_template('home.html')

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
    """
    Sets the case status property of each item in the results list.

    Args:
        results (list): List of items founds during search.
        case_id (str): _id property of case document in the cases collection.
        categor (str): The category or category:sub_category of the items in *results*.

    Return:
        None. The *results* list is modified in place.
    """
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

        if 'case' in session:
            filter_results(results, session['case']['_id'], "PERSON")
        results = sorted(results, key = lambda i: (i.case_status, i.driver_name))
        return render_template('drivers.html', drivers=results)

    form = request.form
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
    if 'case' in session:
        case_id = session['case']['_id']
    else:
        case_id = None
    search_type = form["search_type"]
    net_results = {}

    if form["owner_name"]:
        (success, message, results) = WEBSERVICE.dmv_name(pd_credentials(session), search_terms=form['owner_name'], us_state=form['state'])
        print("Found {} records for {} search for '{}'.".format(len(results), "owner_name", form["owner_name"]))
        if case_id:
            filter_results(results, case_id, "PROPERTY:VEHICLE")
        net_results = join_results(search_type, net_results, results)

    if form["plate"]:
        (success, message, results) = WEBSERVICE.dmv_plate(pd_credentials(session), search_terms=form['plate'], us_state=form['state'])
        print("Found {} records for {} search for '{}'.".format(len(results), "plate", form["plate"]))
        if case_id:
            filter_results(results, case_id, "PROPERTY:VEHICLE")
        net_results = join_results(search_type, net_results, results)

    if form["vin"]:
        (success, message, results) = WEBSERVICE.dmv_vin(pd_credentials(session), search_terms=form['vin'], us_state=form['state'])
        print("Found {} records for {} search for '{}'.".format(len(results), "vin", form["vin"]))
        if case_id:
            filter_results(results, case_id, "PROPERTY:VEHICLE")
        net_results = join_results(search_type, net_results, results)

    if form["search"]:
        (success, message, results) = WEBSERVICE.dmv_any(pd_credentials(session), search_terms=form['search'], us_state=form['state'])
        print("Found {} records for {} search for '{}'.".format(len(results), "any", form["search"]))
        if case_id:
            filter_results(results, case_id, "PROPERTY:VEHICLE")
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