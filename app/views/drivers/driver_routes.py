"""
driver_routes.py - Handle the routes for searching and displaying drivers.

This module provides the views for the following routes:

/driver/<string:db>/<string:ed>/<string:rec>/<string:state>/
/search/dl_address
/search/dl

Copyright (c) 2019 by Thomas J. Daley. All Rights Reserved.
"""

from flask import Blueprint, render_template, redirect, request, session, flash, url_for, jsonify
import random
from passlib.hash import sha256_crypt

from views.decorators import is_logged_in, is_case_set

from webservice import WebService
WEBSERVICE = None


# Helper to create Public Data credentials from session variables
def pd_credentials(mysession)->dict:
    return {"username": session["pd_username"], "password": session["pd_password"]}


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

        # if 'case' in session:
        #    filter_results(results, session['case']['_id'], "PERSON")
        results = sorted(results, key=lambda i: (i.case_status, i.driver_name))
        return render_template('drivers.html', drivers=results)

    form = request.form
    return render_template("search_error.html", formvariables=form, operation="Search: DL", message=message)

driver_routes = Blueprint("driver_routes", __name__, template_folder="templates")


@driver_routes.route('/search/dl_address', methods=['GET'])
@is_logged_in
def search_dl_address():
    search_type = "main"
    search_terms = request.args.get('a')
    search_state = request.args.get('s').lower()
    return search_drivers(search_type, search_terms, search_state)


@driver_routes.route('/search/dl', methods=['GET', 'POST'])
@is_logged_in
def search_dl():
    if request.method == 'GET':
        return render_template('search_dl.html')

    form = request.form
    search_type = form["search_type"]
    search_terms = form["search_terms"]
    search_state = form["state"]
    return search_drivers(search_type, search_terms, search_state)


@driver_routes.route('/driver/<string:db>/<string:ed>/<string:rec>/<string:state>/', methods=['GET'])
@is_logged_in
def driver_details(db, ed, rec, state):
    (success, message, result) = WEBSERVICE.driver_details(pd_credentials(session), db, ed, rec, state)
    if success:
        return render_template('driver.html', driver=result)
    return render_template("search_error.html", formvariables=[], operation="Search: DL Details", message=message)
