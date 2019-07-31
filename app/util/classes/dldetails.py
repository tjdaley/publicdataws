"""
dldetails.py - Standard representation of a Driver's License record.

Copyright (c) 2019 by Thomas J. Daley, J.D.
"""
__author__ = "Thomas J. Daley, J.D."
__version__ = "0.0.1"

import re
import xml.etree.ElementTree as ET

from .baserecord import BaseRecord

def clean_string(s):
    # Remove punctuation
    result = re.sub(r'[.,#!$%^&*;:{}=\-_`~()]', ' ', s)

    # Remove any resulting multiple spaces
    result = re.sub(r'\s{2,}', ' ', result)
    return result

def make_street_link(s):
    return re.sub(r'\s', '+', clean_string(s))

class DlDetails(BaseRecord):
    """
    Driver's License record.
    """
    MAPPINGS = {}
    MAPPINGS["PUBLICDATA"] = {}
    MAPPINGS["PUBLICDATA"]["TX"] = [
        {"label": "First Name", "attr": "first_name", "transform": clean_string},
        {"label": "Middle Name", "attr": "middle_name", "transform": clean_string},
        {"label": "Last Name", "attr": "last_name", "transform": clean_string},
        {"label": "Name Suffix", "attr": "suffix", "transform": clean_string},
        {"label": "Address", "attr": "address"},
        {"label": "Address", "attr": "linkable_address", "transform": make_street_link},
        {"label": "Address(Continued)", "attr": "address"},
        {"label": "City/ZIP Code", "attr": "city"},
        {"label": "DOB", "attr": "dob"},
        {"label": "License number", "attr": "license_number"},
        {"label": "License type", "attr": "license_type"},
        {"label": "Issue Date", "prop": "formatteddate", "attr": "issue_date"}
    ]

    def __init__(self):
        """
        Initialize an instance.
        """
        self.first_name = None
        self.middle_name = None
        self.last_name = None
        self.suffix = None

        self.address = None
        self.linkable_address = None
        self.city = None
        self.state = None
        self.dob = None

        self.license_number = None
        self.license_type = None
        self.issue_date = None

    def __str__(self):
        return "{} {} {} {} {}".format(
            self.first_name, self.middle_name, self.last_name, self.suffix, self.dob
        )
               