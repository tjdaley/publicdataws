"""
app.py - Flask-based server.

Copyright (c) 2019 by Thomas J. Daley, J.D.
"""
__author__ = "Thomas J. Daley, J.D."
__version__ = "0.0.1"

import argparse
import random
from flask import Flask, render_template, request, flash, redirect, url_for, session, logging
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
from functools import wraps

from data import Articles
ARTICLES = Articles()

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

# Helper to create Public Data credentials from session variables
def pd_credentials(mysession)->dict:
    return {"username": session["pd_username"], "password": session["pd_password"]}

@app.route('/', methods=['GET'])
def index():
    return render_template('home.html')

@app.route('/about', methods=['GET'])
def about():
    return render_template('about.html')

@app.route('/search/people', methods=['GET'])
@is_logged_in
def search_people_get():
    return render_template('search_people.html')

@app.route('/search/dmv', methods=['GET', 'POST'])
@is_logged_in
def search_dmv_get():
    if request.method == 'GET':
        return render_template('search_dmv.html')
    else:
        form = request.form
        (success, message, results) = WEBSERVICE.dmv_name(pd_credentials(session), form['owner_name'])
        if success:
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

@app.route('/articles', methods=['GET'])
def articles():
    return render_template('articles.html', articles=ARTICLES)

@app.route('/article/<string:id>/', methods=['GET'])
def article(id):
    return render_template('article.html', id=id)

class RegisterForm(Form):
    name = StringField("Name", [validators.DataRequired(), validators.Length(min=1, max=50)])
    email = StringField("Email", [validators.Length(min=6, max=50)])
    password = PasswordField("Password", [
        validators.DataRequired(),
        validators.EqualTo('confirm', "Passwords do no match.")
        ])
    confirm = PasswordField("Confirm password")
    pd_username = StringField("Public Data username", validators=[validators.Required()])
    pd_password = StringField("Public Data password", validators=[validators.Required()])
    zillow_key = StringField("Zillow API key", validators=[validators.Required()])

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)

    if request.method == 'POST' and form.validate():
        fields = request.form
        myfields = {key:value for (key, value) in fields.items()}
        myfields["password"] = sha256_crypt.hash(str(fields["password"]))
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
    pd_username = StringField("Public Data username", validators=[validators.Required()])
    pd_password = StringField("Public Data password", validators=[validators.Required()])
    zillow_key = StringField("Zillow API key", validators=[validators.Required()])

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
    parser.add_argument("--zillowid", "-z", help="Zillow API credential from https://www.zillow.com/howto/api/APIOverview.htm")
    args = parser.parse_args()

    WEBSERVICE = WebService(args.zillowid)
    app.secret_key="SDFIIUWER*HGjdf8*"
    app.run(debug=True)