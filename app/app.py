"""
app.py - Flask-based server.

Copyright (c) 2019 by Thomas J. Daley, J.D.
"""
__author__ = "Thomas J. Daley, J.D."
__version__ = "0.0.1"

import argparse
import random
from flask import Flask, render_template, request, flash, redirect, url_for, session, logging, make_response, jsonify
from wtforms import Form, StringField, TextAreaField, PasswordField, validators

from functools import wraps

from views.decorators import is_admin_user, is_logged_in, is_case_set

from webservice import WebService
WEBSERVICE = None

from util.database import Database
DATABASE = Database()
DATABASE.connect()

app = Flask(__name__)

# Helper to create Public Data credentials from session variables
def pd_credentials(mysession)->dict:
    return {"username": session["pd_username"], "password": session["pd_password"]}

# Load routes defined in the views folder
from views.login.login import login
app.register_blueprint(login)

from views.info.info_routes import info_routes
app.register_blueprint(info_routes)

from views.cases.case_routes import case_routes
app.register_blueprint(case_routes)

from views.admin.admin_routes import admin_routes
app.register_blueprint(admin_routes)

from views.drivers.driver_routes import driver_routes
app.register_blueprint(driver_routes)

from views.vehicles.vehicle_routes import vehicle_routes
app.register_blueprint(vehicle_routes)

from views.real_property.real_property_routes import rp_routes
app.register_blueprint(rp_routes)

print(app.url_map)

@app.route('/', methods=['GET'])
def index():
    return render_template('home.html')

if __name__ == "__main__":
    #global WEBSERVICE
    parser = argparse.ArgumentParser(description="Webservice for DiscoveryBot")
    parser.add_argument("--debug", help="Run server in debug mode", action='store_true')
    parser.add_argument("--port", help="TCP port to listen on", type=int, default=5001)
    parser.add_argument("--zillowid", "-z", help="Zillow API credential from https://www.zillow.com/howto/api/APIOverview.htm")
    args = parser.parse_args()

    WEBSERVICE = WebService(args.zillowid)
    app.secret_key="SDFIIUWER*HGjdf8*"
    app.run(debug=args.debug, port=args.port)