"""
real_property_routes.py - Handle the routes for searching and displaying real
                          property.

This module provides the views for the following routes:

/search/rp

Copyright (c) 2019 by Thomas J. Daley. All Rights Reserved.
"""

from flask import Blueprint, flash, render_template, redirect, request, session, url_for
import random
from passlib.hash import sha256_crypt
from operator import itemgetter

from views.decorators import is_logged_in, is_case_set

from webservice import WebService
WEBSERVICE = WebService(None)

# from util.database import Database
# DATABASE = Database()
# DATABASE.connect()


# Helper to create Public Data credentials from session variables
def pd_credentials(mysession)->dict:
    return {
        "username": session["pd_username"],
        "password": session["pd_password"]
        }


def search(search_type, search_terms, search_state):
    (success, message, results) = WEBSERVICE.tax_records(
        pd_credentials(session),
        search_terms=search_terms,
        match_scope=search_type,
        us_state=search_state)

    if success:
        if not results:
            message = """
            No properties found that match ALL the search criteria. This can be for two reasons:
            (1) There really aren't any properties that match the combined search criteria; or
            (2) The search criteria were too broad which resulted in the search results to be truncated thus
            reducing the number of properties that matched all criteria. If you used a criterion in the "entire record"
            field that would return more than 1000 results, the second explanation probably applies.
            """
            flash(message, "warning")
            return redirect(url_for('rp_routes.search_rp'))

        flash("Found {} matching properties.".format(len(results)), "success")

        # if 'case' in session:
        #    filter_results(results, session['case']['_id'], "PERSON")
        results = sorted(results, key=itemgetter('owner'))
        return render_template('properties.html', properties=results)

    form = request.form
    return render_template("search_error.html", formvariables=form, operation="Search: RP", message=message)

rp_routes = Blueprint("rp_routes", __name__, template_folder="templates")


@rp_routes.route('/search/rp', methods=['GET', 'POST'])
@is_logged_in
def search_rp():
    if request.method == 'GET':
        return render_template('search_rp.html')

    form = request.form
    search_type = form["search_type"]
    search_terms = form["search_terms"]
    search_state = form["state"]
    return search(search_type, search_terms, search_state)


@rp_routes.route('/property/<string:db>/<string:ed>/<string:rec>/<string:state>/', methods=['GET'])
@is_logged_in
def property_details(db, ed, rec, state):
    zwsid = session['zillow_key']

    if zwsid:
        get_zillow = True
    else:
        get_zillow = False

    (success, message, result) = WEBSERVICE.property_details(pd_credentials(session), db, ed, rec, state, get_zillow, zwsid)
    if success:
        return render_template('property.html', prop=result)
    return render_template("search_error.html", formvariables=[], operation="Search: RP Details", message=message)
