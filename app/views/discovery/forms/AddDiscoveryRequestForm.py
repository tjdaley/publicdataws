"""
AddDiscoveryReqeustForm.py - Add a discovery request to a discovery document.

Copyright (c) 2019 by Thomas J. Daley. All Rights Reserved.
"""
from wtforms import Form, StringField, TextAreaField, validators


class AddDiscoveryRequstItemForm(Form):
    # number = StringField("Request number", [validators.required])
    request = TextAreaField("Request", [validators.length(min=10, max=4096)])
