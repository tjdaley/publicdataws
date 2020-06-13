"""
login.py - Handle the login/logout routes.

This module provides the views for the following routes:

/login
/logout
/register
/settings

Copyright (c) 2019 by Thomas J. Daley. All Rights Reserved.
"""

from flask import Blueprint, render_template, redirect, request, session, flash, url_for
import random
from passlib.hash import sha256_crypt

from views.decorators import is_logged_in

from .forms.RegisterForm import RegisterForm
from .forms.SettingsForm import SettingsForm

from util.database import Database
DATABASE = Database()
DATABASE.connect()

login = Blueprint("login", __name__, template_folder="templates")


@login.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)

    if request.method == 'POST' and form.validate():
        fields = request.form
        myfields = {key: value for (key, value) in fields.items()}
        myfields["password"] = sha256_crypt.hash(str(fields["password"]))
        del myfields["confirm"]  # saving that to the db defeats the purpose of encryption
        success = DATABASE.add_user(myfields)
        if success:
            flash("Your registration has been saved--Please login.", 'success')
            return redirect(url_for('login.do_login'))

        flash("{} is already registered.".format(fields["email"]), 'danger')
        return redirect(url_for('login.register'))

    return render_template('register.html', form=form)


@login.route('/settings', methods=['GET', 'POST'])
@is_logged_in
def settings():
    myfields = {"email": session['email']}
    result = DATABASE.get_user(myfields)
    myfields = {key: value for (key, value) in result.items() if key != "password"}
    form = SettingsForm(**myfields)

    # Email not found - something fishy is going on.
    if not result:
        message = "Oddly, {} is not registered as a user.".format(myfields['email'])
        flash(message, "danger")
        return redirect(url_for("login.do_logout"))

    if request.method == 'POST':
        # Email found - do passwords match?
        password_candidate = request.form["password"]
        if sha256_crypt.verify(password_candidate, result["password"]):
            # Yes, passwords match
            messages = ["Your settings have been updated.", "Your settings are updated.", "Your changes have been saved."]
            message = random.choice(messages)
            fields = request.form
            myfields = {key: value for (key, value) in fields.items() if key != "password" and value}
            myfields['email'] = session['email']
            session['pd_username'] = myfields['pd_username']
            session['pd_password'] = myfields['pd_password']
            session['zillow_key'] = myfields['zillow_key']
            DATABASE.update_user(myfields)
            return render_template("home.html", msg=message)

    return render_template('settings.html', form=form, old_data=result)


@login.route('/login', methods=['GET', 'POST'])
def do_login():
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


@login.route("/logout", methods=["GET"])
def do_logout():
    session.clear()
    messages = ["Good bye!!", "Hope to see you again soon.", "Thank you for visiting!!"]
    flash(random.choice(messages), "success")
    return redirect(url_for('login.do_login'))
