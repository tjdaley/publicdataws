"""
objection_routes.py - Handle the routes for objection requests

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

objection_routes = Blueprint('objection_routes', __name__, template_folder='templates')


# Helper to create Public Data credentials from session variables
def pd_credentials(mysession) -> dict:
    return {"username": session["pd_username"], "password": session["pd_password"]}


@objection_routes.route('/objection/list/<string:scope>', methods=['GET'])
@objection_routes.route('/objection/list', methods=['GET'])
@is_logged_in
def objection_list(scope='all'):
    """
    Show all objections that apply_to the specified discovery type (scope)
    or all if scope is omitted.
    """
    objections = DATABASE.get_objection_list({'scope': scope})
    return render_template(
        'objection_list.html',
        docs=objections,
        scope=scope,
    )


@objection_routes.route('/objection/template/add', methods=['GET', 'POST'])
@objection_routes.route('/objection/template/edit/<string:id>', methods=['GET', 'POST'])
@is_logged_in
@is_admin_user
def objection_template(id=None):
    """
    Add or edit an objection template.
    """
    form = AddObjectionTemplateForm(request.form)

    if request.method == 'POST' and form.validate():
        fields = request.form
        myfields = {key: value for (key, value) in fields.items()}
        myfields['email'] = session['email']
        myfields['applies_to'] = request.form.getlist('applies_to')
        success = DATABASE.save_objection_template(myfields)
        if '_id' in myfields:
            operation = "updated"
        else:
            operation = "added"
        if success:
            flash("\"{}\" {}.".format(myfields['label'], operation), "success")
            return redirect(url_for('objection_routes.objection_list'))
        flash("Failed to save objection template. Check log for explanation.", "danger")
        return redirect(url_for('objection_routes.objection_list'))

    if id:
        fields = {'id': id}
        doc = DATABASE.get_objection_template(fields)
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
        'objection_template.html',
        form=AddObjectionTemplateForm(
            template=doc['template'],
            applies_to=doc['applies_to']
        ),
        document=doc
    )


@objection_routes.route('/objection/template/delete', methods=['POST'])
@is_logged_in
@is_admin_user
def del_objection_template():
    id_ = request.form.get('id')
    success = DATABASE.del_objection_template({'id': id_})
    return jsonify({"success": success, "message": "Nothing to say."})


@objection_routes.route('/objection/text', methods=['POST'])
@is_logged_in
def get_objection_text():
    """
    Client sends a list of objection ids, we respond
    with a dictionary of id:text elements.
    """
    objection_labels = request.form.getlist('objections[]')
    result = []
    for label in objection_labels:
        objection_text = DATABASE.get_objection_text(label)
        result.append({'label': label, 'text': objection_text})
    return jsonify({'success': True, 'message': "OK", 'objections': result})


@objection_routes.route('/objection/list', methods=['POST'])
@is_logged_in
def get_objection_list():
    """
    Get a list of objections pertinant to the type of discovery indicated.
    """
    discovery_type = request.form.get('type')
    result = []
    objections = DATABASE.get_objection_list({'scope': discovery_type})
    for objection in objections:
        result.append({'label': objection['label'], 'text': objection['short_text']})
    return jsonify({'success': True, 'message': "OK", 'objections': result})
