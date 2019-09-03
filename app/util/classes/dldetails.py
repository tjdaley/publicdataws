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

def fl_first_name(s):
    # Sample input: "PAXTON,ERIC JAMES"
    parts = s.split(",")
    if len(parts) != 2:
        return s

    parts = parts[1].split(" ", 2)
    return parts[0].strip()

def fl_middle_name(s):
    # Sample input: "PAXTON,ERIC JAMES"
    parts = s.split(",")
    if len(parts) != 2:
        return s

    parts = parts[1].split(" ", 2)
    return parts[1].strip()

def fl_last_name(s):
    # Sample input: "PAXTON,ERIC JAMES"
    parts = s.split(",")
    if len(parts) != 2:
        return s

    return parts[0].strip()

def fl_suffix_name(s):
    pass

def tx_city(s):
    # Extract the city name
    # Example input: "LITTLE ELM 90210"
    parts = s.split(" ")
    return " ".join(parts[0:-1])

def tx_zip_code(s):
    # Extract the ZIP Code
    # Example input: "MCKINNEY 75070"
    parts = s.split(" ")
    return parts[-1]

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
        {"label": "City/ZIP Code", "attr": "city", "transform": tx_city},
        {"label": "City/ZIP Code", "attr": "zip_code", "transform": tx_zip_code},
        {"label": "DOB", "prop": "formatteddate", "attr": "dob"},
        {"label": "License number", "attr": "license_number"},
        {"label": "License type", "attr": "license_type"},
        {"label": "Issue Date", "prop": "formatteddate", "attr": "issue_date"}
    ]

    MAPPINGS["PUBLICDATA"]["FL"] = [
        {"label": "Name", "attr": "first_name", "transform": fl_first_name},
        {"label": "Name", "attr": "middle_name", "transform": fl_middle_name},
        {"label": "Name", "attr": "last_name", "transform": fl_last_name},
        {"label": "Name", "attr": "suffix", "transform": fl_suffix_name},
        {"label": "Address", "attr": "address"},
        {"label": "Address", "attr": "linkable_address", "transform": make_street_link},
        {"label": "City", "attr": "city"},
        {"label": "ZIP Code", "attr": "zip_code"},
        {"label": "Date of Birth", "prop": "formatteddate", "attr": "dob"},
        {"label": "DL Number", "attr": "license_number"},
        {"label": "Type", "attr": "license_type"},
        {"label": "Issue Date", "prop": "formatteddate", "attr": "issue_date"},
        {"label": "Race", "attr": "race"},
        {"label": "Sex", "attr": "sex"},
        {"label": "Height", "attr": "height"}
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
        self.zip_code = None
        self.race = None
        self.sex = None
        self.height = None
        self.dob = None

        self.license_number = None
        self.license_type = None
        self.issue_date = None

    def __str__(self):
        return "{} {} {} {} {}".format(
            self.first_name, self.middle_name, self.last_name, self.suffix, self.dob
        )
               