"""
case_routes.py - Handle the login/logout routes.

This module provides the views for the following routes:

/case/add
/case/items
/case/update_items
/case/<string:id>
/cases
/clearcaseid
/setcaseid

Copyright (c) 2019 by Thomas J. Daley. All Rights Reserved.
"""

from flask import Blueprint, render_template, redirect, request, session, flash, url_for, jsonify
import random
from passlib.hash import sha256_crypt

from views.decorators import is_logged_in, is_case_set

from .forms.AddCaseForm import AddCaseForm

from util.database import Database
DATABASE = Database()
DATABASE.connect()

case_routes = Blueprint("case_routes", __name__, template_folder="templates")


@case_routes.route("/case/items/", methods=['GET'])
@is_logged_in
@is_case_set
def get_case_items():
    case_id = session['case']['_id']
    case_items = DATABASE.get_case_items(session['email'], case_id=case_id)
    return render_template("case_discovery_list.html", discovery=case_items, case_id=case_id)


@case_routes.route('/case/add/', methods=['GET', 'POST'])
@is_logged_in
def add_case():
    form = AddCaseForm(request.form)

    if request.method == 'POST' and form.validate():
        fields = request.form
        myfields = {key: value for (key, value) in fields.items()}
        myfields["email"] = session["email"]
        myfields["created_by"] = session["email"]
        success = DATABASE.add_case(myfields)
        if success:
            flash("Case {} added.".format(myfields["cause_number"]), 'success')
            return redirect(url_for('case_routes.list_cases'))
        flash("Failed to add case. Check log for explanation.", "danger")
        return redirect(url_for("case_routes.add_case"))

    return render_template('case.html', form=form)


@case_routes.route('/cases', methods=['GET'])
@is_logged_in
def list_cases():
    cases = DATABASE.get_cases({"email": session["email"]})
    return render_template('cases.html', cases=cases)


@case_routes.route('/case/update_items/', methods=['POST'])
@is_logged_in
@is_case_set
def update_case_items():
    fields = request.form
    item = {key: value for (key, value) in fields.items() if key not in ['case_id', 'category', 'key', 'operation']}
    case_id = session['case']['_id']
    category = fields['category']
    key = fields['key']
    description = fields['description']
    operation = fields['op'].lower()

    if operation == "add":
        # Add to the included list and remove from the excluded list.
        success = DATABASE.add_to_case(session['email'], case_id, category, key, item)
        success = DATABASE.del_from_case(session['email'], case_id, "X" + category, key, item)
        return jsonify({"success": success, "message": "Item added: {}".format(description)})
    elif operation == "del":
        success = DATABASE.del_from_case(session['email'], case_id, category, key, item)
        success = DATABASE.add_to_case(session['email'], case_id, "X" + category, key, item)
        return jsonify({"success": success, "message": "Item removed: {}".format(description)})

    message = "Invalid operation: {}".format(operation)
    flash(message, "danger")
    return jsonify({"success": False, "message": message})


@case_routes.route('/case/<string:id>/', methods=['GET', 'POST'])
@is_logged_in
def get_case(id):
    if request.method == 'POST':
        fields = request.form
        myfields = {key: value for (key, value) in fields.items()}
        myfields['_id'] = id
        myfields['email'] = session['email']
        result = DATABASE.update_case(myfields)
        if result:
            return redirect(url_for('case_routes.list_cases'))
        flash("Failed to update case. Check log for explanation.", "danger")
        return redirect(url_for('case_routes.list_cases'))

    # Show the case on a GET request
    case = DATABASE.get_case({"_id": id, "email": session["email"]})
    myfields = {key: value for (key, value) in case.items()}
    form = AddCaseForm(**myfields)
    return render_template("case.html", form=form)


@case_routes.route("/setcaseid/", methods=["POST"])
@is_logged_in
def set_case_id():
    case = DATABASE.get_case({"email": session["email"], "_id": request.form["_id"]})
    case["_id"] = str(case["_id"])
    session["case"] = DATABASE.safe_dict(case)
    status = {"message": "Case is set", "success": True, "is_set": True}
    return jsonify(status)


@case_routes.route("/clearcaseid/", methods=["POST"])
@is_logged_in
def clear_case_id():
    del session["case"]
    return jsonify({"message": "Case is cleared", "success": True, "is_set": False})
