"""
discovery_routes.py - Handle the routes for discovery requests

Copyright (c) 2019 by Thomas J. Daley. All Rights Reserved.
"""

from flask import Blueprint, render_template, redirect, request, session, flash, url_for, jsonify
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
import random
from passlib.hash import sha256_crypt

from views.decorators import is_logged_in, is_case_set
from util.database import Database
from webservice import WebService
from .forms.AddDiscoveryDocumentForm import AddDiscoveryDocumentForm
from .forms.AddDiscoveryRequestForm import AddDiscoveryRequstItemForm

DATABASE = Database()
DATABASE.connect()
WEBSERVICE = WebService(None)

discovery_routes = Blueprint('discovery_routes', __name__, template_folder="templates")


# Helper to create Public Data credentials from session variables
def pd_credentials(mysession) -> dict:
    return {"username": session["pd_username"], "password": session["pd_password"]}


@discovery_routes.route('/discovery/list/<string:scope>')
@discovery_routes.route('/discovery/list/<string:scope>/<string:cause_number>', methods=['GET'])  # NOQA
@is_logged_in
def discovery_list(scope, cause_number=None):
    """
    Show all discovery for a cause number or for all cases owned by this user.
    """
    discovery_docs = DATABASE.get_discovery_list(
        {
            'email': session['email'],
            'scope': scope,
            'cause_number': cause_number,
        }
    )
    return render_template(
        'discovery_list.html',
        docs=discovery_docs,
        scope=scope,
        cause_number=cause_number,
    )


@discovery_routes.route('/discovery/requests/<string:id>', methods=['GET'])
@is_logged_in
def discovery_requests(id):
    """
    List each request for a particular discovery request document.
    """
    discovery_requests = DATABASE.get_discovery_requests(
        {
            'email': session['email'],
            'id': id,
        }
    )
    return render_template(
        'discovery_requests.html',
        doc=discovery_requests,
    )


@discovery_routes.route('/discovery/request/add/<string:id>', methods=['GET', 'POST'])
@is_logged_in
def discovery_request_add(id):
    """
    Add one discovery request to a discovery document.
    """
    form = AddDiscoveryRequstItemForm(request.form)

    if request.method == 'POST' and form.validate():
        fields = request.form
        myfields = {key: value for (key, value) in fields.items()}
        myfields["email"] = session["email"]
        myfields["owner"] = session["email"]
        myfields['request_text'] = myfields['request']
        success = DATABASE.save_discovery_request(myfields)
        if success:
            flash("Request added.", 'success')
            return redirect('/discovery/requests/{}'.format(myfields['id']))
        flash("Failed to add case. Check log for explanation.", "danger")
        return redirect('/discovery/requests/{}'.format(myfields['id']))

    return render_template('discovery_request_add.html', case_id=id, form=form)


@discovery_routes.route('/discovery/document/add', methods=['GET', 'POST'])
@discovery_routes.route('/discovery/document/edit/<string:id>', methods=['GET', 'POST'])
@is_logged_in
def discovery_document_edit(id=None):
    form = AddDiscoveryDocumentForm(request.form)

    if request.method == 'POST' and form.validate():
        fields = request.form
        myfields = {key: value for (key, value) in fields.items()}
        myfields["email"] = session["email"]
        myfields["owner"] = session["email"]
        success = DATABASE.save_discovery_document(myfields)
        if success:
            flash("{} added.".format(myfields["discovery_type"]), 'success')
            return redirect(url_for('discovery_list'))
        flash("Failed to add case. Check log for explanation.", "danger")
        return redirect(url_for('discovery_list'))

    if id:
        fields = {'email': session['email'], 'id': id}
        doc = DATABASE.get_discovery_document(fields)
    else:
        doc = {
            '_id': None,
            'court_type': '',
            'court_number': '',
            'county': '',
            'cause_number': '',
            'discovery_type': '',
            'owner': session['email'],
            'requesting_attorney': {'bar_number': '', 'email': ''}
        }
    return render_template('discovery_document.html', form=form, document=doc)


@discovery_routes.route('/discovery/document/delete', methods=['POST'])
@is_logged_in
def discovery_document_delete():
    """
    Delete one discovery document.
    """
    fields = request.form
    myfields = {key: value for (key, value) in fields.items()}
    myfields['email'] = session['email']
    success = DATABASE.del_discovery_document(myfields)
    return jsonify({"success": success, "message": "Nothing to say."})


@discovery_routes.route('/discovery/document/set_cleaned_flag', methods=['POST'])
@is_logged_in
def discovery_document_set_cleaned_flag():
    """
    Set or clear the cleaned_up flag.
    """
    fields = request.form
    myfields = {key: value for (key, value) in fields.items()}
    myfields['email'] = session['email']
    myfields['key'] = 'cleaned_up'
    myfields['value'] = int(myfields['value'])
    success = DATABASE.update_discovery_document_field(myfields)
    return jsonify({"success": success, "message": "Nothing to say."})


@discovery_routes.route('/discovery/document/set_field', methods=['POST'])
@is_logged_in
def discovery_document_set_field():
    """
    Set one field in a discovery document.
    """
    fields = request.form
    myfields = {key: value for (key, value) in fields.items()}
    myfields["email"] = session["email"]
    success = DATABASE.update_discovery_document_field(myfields)
    return jsonify({"success": success, "message": "Nothing to say."})


@discovery_routes.route('/discovery/request/save', methods=['POST'])
@is_logged_in
def discovery_request_save():
    """
    Save an individual discovery request within a discovery request document.
    """
    fields = request.form
    myfields = {key: value for (key, value) in fields.items()}
    myfields['email'] = session['email']
    success = DATABASE.save_discovery_request(myfields)
    return jsonify({"success": success, "message": "Nothing to say."})


@discovery_routes.route('/discovery/request/delete', methods=['POST'])
@is_logged_in
def del_discovery_request():
    """
    Delete an individual discovery request within a discovery request document.
    """
    fields = request.form
    myfields = {key: value for (key, value) in fields.items()}
    myfields['email'] = session['email']
    success = DATABASE.del_discovery_request(myfields)
    return jsonify({"success": success, "message": "Nothing to say."})
