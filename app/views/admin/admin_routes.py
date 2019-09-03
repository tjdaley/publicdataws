"""
admin_routes.py - Handle the administrative routes.

This module provides the views for the following routes:

/query
/queries

Copyright (c) 2019 by Thomas J. Daley. All Rights Reserved.
"""
from flask import Blueprint, render_template

from views.decorators import is_logged_in, is_admin_user

from util.database import Database
DATABASE = Database()
DATABASE.connect()

admin_routes = Blueprint("admin_routes", __name__, template_folder="templates")

@admin_routes.route("/queries", methods=['GET'])
@is_logged_in
@is_admin_user
def list_query_cache():
    queries = DATABASE.get_query_cache(50)
    return render_template("queries.html", queries=queries)

@admin_routes.route("/query/<string:id>/", methods=['GET'])
@is_logged_in
@is_admin_user
def show_query(id):
    result = DATABASE.get_query_cache_item_result(id)
    return render_template("query_result.html", result=result)
