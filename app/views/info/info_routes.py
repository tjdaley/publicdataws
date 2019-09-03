"""
info_routes.py - Handle the routes for basic information pages.

This module provides the views for the following routes:

/about
/privacy
/terms_and_conditions

Copyright (c) 2019 by Thomas J. Daley. All Rights Reserved.
"""

from flask import Blueprint, render_template

info_routes = Blueprint("info_routes", __name__, template_folder="templates")

@info_routes.route('/about', methods=['GET'])
def about():
    return render_template('about.html')

@info_routes.route("/privacy/", methods=["GET"])
def privacy():
    return render_template("privacy.html")

@info_routes.route("/terms_and_conditions", methods=["GET"])
def terms_and_conditions():
    return render_template("terms_and_conditions.html")

