"""
response_routes.py - Handle the routes for objection requests

Copyright (c) 2019 by Thomas J. Daley. All Rights Reserved.
"""

from flask import Blueprint, render_template, redirect, request, session, flash, url_for, jsonify
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
import random

from views.decorators import is_logged_in, is_case_set, is_admin_user
from util.database import Database
from .forms.AddObjectionTemplateForm import AddObjectionTemplateForm

DATABASE = Database()
DATABASE.connect()

response_routes = Blueprint('response_routes', __name__, template_folder='templates')


# Helper to create Public Data credentials from session variables
def pd_credentials(mysession) -> dict:
    return {"username": session["pd_username"], "password": session["pd_password"]}


@response_routes.route('/response/list/<string:scope>', methods=['GET'])
@response_routes.route('/response/list', methods=['GET'])
@is_logged_in
def response_list(scope='all'):
    """
    Show all responses that apply_to the specified discovery type (scope)
    or all if scope is omitted.
    """
    responses = DATABASE.get_response_list({'scope': scope})
    return render_template(
        'response_list.html',
        docs=responses,
        scope=scope,
    )


@response_routes.route('/response/template/add', methods=['GET', 'POST'])
@response_routes.route('/response/template/edit/<string:id>', methods=['GET', 'POST'])
@is_logged_in
@is_admin_user
def response_template(id=None):
    """
    Add or edit a response template.
    """
    form = AddResponseTemplateForm(request.form)

    if request.method == 'POST' and form.validate():
        fields = request.form
        myfields = {key: value for (key, value) in fields.items()}
        myfields['email'] = session['email']
        myfields['applies_to'] = request.form.getlist('applies_to')
        success = DATABASE.save_response_template(myfields)
        if '_id' in myfields:
            operation = "updated"
        else:
            operation = "added"
        if success:
            flash("\"{}\" {}.".format(myfields['label'], operation), "success")
            return redirect(url_for('response_routes.response_list'))
        flash("Failed to save response template. Check log for explanation.", "danger")
        return redirect(url_for('response_routes.response_list'))

    if id:
        fields = {'id': id}
        doc = DATABASE.get_response_template(fields)
    else:
        doc = {
            '_id': None,
            'label': '',
            'short_text': '',
            'applies_to': [],
            'template': '',
        }
    # NOTE: The arguments in form instantiation to prepopulate the textarea widget.
    return render_template(
        'response_template.html',
        form=AddResponseTemplateForm(
            template=doc['template'],
            applies_to=doc['applies_to']
        ),
        document=doc
    )


@response_routes.route('/response/template/delete', methods=['POST'])
@is_logged_in
@is_admin_user
def del_response_template():
    id_ = request.form.get('id')
    success = DATABASE.del_response_template({'id': id_})
    return jsonify({"success": success, "message": "Nothing to say."})


@response_routes.route('/response/text', methods=['POST'])
@is_logged_in
def get_response_text():
    """
    Client sends a list of response ids, we respond
    with a dictionary of id:text elements.
    """
    response_labels = request.form.getlist('responses[]')
    result = []
    for label in response_labels:
        response_text = DATABASE.get_response_text(label)
        result.append({'label': label, 'text': response_text})
    return jsonify({'success': True, 'message': "OK", 'responses': result})


@response_routes.route('/response/list', methods=['POST'])
@is_logged_in
def get_response_list():
    """
    Get a list of responses pertinant to the type of discovery indicated.
    """
    discovery_type = request.form.get('type')
    result = []
    responses = DATABASE.get_response_list({'scope': discovery_type})
    for response in responses:
        result.append({'label': response['label'], 'text': response['short_text']})
    return jsonify({'success': True, 'message': "OK", 'responses': result})
