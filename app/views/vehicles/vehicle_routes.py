"""
vehicle_routes.py - Handle the routes for searching and displaying motor vehicles.

This module provides the views for the following routes:

/vehicle/<string:db>/<string:ed>/<string:rec>/<string:state>/
/search/dmv

Copyright (c) 2019 by Thomas J. Daley. All Rights Reserved.
"""

from flask import Blueprint, render_template, redirect, request, session, flash, url_for, jsonify
import random
from passlib.hash import sha256_crypt

from views.decorators import is_logged_in, is_case_set

from webservice import WebService
from util.database import Database

WEBSERVICE = WebService(None)

DATABASE = Database()
DATABASE.connect()


# Helper to create Public Data credentials from session variables
def pd_credentials(mysession)->dict:
    return {"username": session["pd_username"], "password": session["pd_password"]}


def join_results(search_type: str, prior_results: dict, new_results: list)->dict:
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
        merged_result = {key: prior_results[key] for key in prior_results.keys() & new_results_dict.keys()}
    else:
        merged_result = new_results_dict
    return merged_result


def filter_results(results: list, case_id: str, category: str):
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

vehicle_routes = Blueprint("vehicle_routes", __name__, template_folder="templates")


@vehicle_routes.route('/search/dmv', methods=['GET', 'POST'])
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
    search_fns = {
        "name": WEBSERVICE.dmv_name,
        "plate": WEBSERVICE.dmv_plate,
        "vin": WEBSERVICE.dmv_vin,
        "any": WEBSERVICE.dmv_any
    }

    search_fn = search_fns[search_type]
    credentials = pd_credentials(session)
    (success, message, search_results) = search_fn(credentials, search_terms=form["search_terms"], us_state=form["state"])
    print("Found {} records for {} search for '{}'.".format(len(search_results), search_type, form["search_terms"]))
    if case_id:
        filter_results(search_results, case_id, "PROPERTY:VEHICLE")

    if success:
        # results = [search_results[key] for key in search_results.keys()]
        results = sorted(search_results, key=lambda i: (i.case_status, i.year_make_model))

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


@vehicle_routes.route('/vehicle/<string:db>/<string:ed>/<string:rec>/<string:state>/', methods=['GET'])
@is_logged_in
def vehicle_details(db, ed, rec, state):
    (success, message, result) = WEBSERVICE.dmv_details(pd_credentials(session), db, ed, rec, state)
    if success:
        return render_template('vehicle.html', vehicle=result)
    return render_template("search_error.html", formvariables=[], operation="Search: DMV Details", message=message)
