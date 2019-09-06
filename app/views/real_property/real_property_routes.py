"""
real_property_routes.py - Handle the routes for searching and displaying real
                          property.

This module provides the views for the following routes:

/search/rp

Copyright (c) 2019 by Thomas J. Daley. All Rights Reserved.
"""

from flask import Blueprint, render_template, redirect, request, session
import random
from passlib.hash import sha256_crypt

from views.decorators import is_logged_in, is_case_set

from webservice import WebService
WEBSERVICE = None

# from util.database import Database
# DATABASE = Database()
# DATABASE.connect()


# Helper to create Public Data credentials from session variables
def pd_credentials(mysession)->dict:
    return {
        "username": session["pd_username"],
        "password": session["pd_password"]
        }

rp_routes = Blueprint("rp_routes", __name__, template_folder="templates")


@rp_routes.route('/search/rp', methods=['GET'])
@is_logged_in
def search_rp_get():
    return render_template('search_rp.html')
