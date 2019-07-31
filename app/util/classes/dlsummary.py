"""
dlsummary.py - Standard representation of a Driver's License summary record.

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

MAPPINGS = {}
MAPPINGS["PUBLICDATA"] = {}
MAPPINGS["PUBLICDATA"]["TX"] = [
    {"path": "./disp_fld1", "attr": "driver_name", "transform": clean_string},
    {"path": "./disp_fld2", "attr": "dob", "transform": None},
    {"path": "./source", "attr": "data_source", "transform": None},
    {"path": ".", "prop": "db", "attr": "db", "transform": None},
    {"path": ".", "prop": "ed", "attr": "ed", "transform": None},
    {"path": ".", "prop": "rec", "attr": "rec", "transform": None}
]
MAPPINGS["PUBLICDATA"]["CO"] = [
    {"path": "./disp_fld1", "attr": "owner_name", "transform": None},
    {"path": "./disp_fld2", "attr": "year_make_model", "transform": None},
    {"path": "./source", "attr": "data_source", "transform": None},
    {"path": ".", "prop": "db", "attr": "db", "transform": None},
    {"path": ".", "prop": "ed", "attr": "ed", "transform": None},
    {"path": ".", "prop": "rec", "attr": "rec", "transform": None}
]

class DlSummary(BaseRecord):
    """
    Driver's License record.
    """
    def __init__(self):
        """
        Initialize an instance.
        """
        self.driver_name = None
        self.dob = None

        self.data_source = None
        self.db = None
        self.ed = None
        self.rec = None
        self.source = None
        self.state = None

    def __str__(self):
        return "Driver name: {} || DOB: {} || Source: {} || State: {}" \
            .format(self.driver_name, self.dob, self.data_source, self.state)

    def from_xml(self, root, source:str, state:str):
        """
        Parses given XML tree into our standard format.

        Args:
            root (ET): XML Root Element for process
            source (str): Source database, e.g. "PUBLICDATA"
            state (str): U.S. State, e.g. "TX"
        """
        if source not in MAPPINGS:
            raise ValueError("No mappings for this source: {}".format(source))

        if state not in MAPPINGS[source]:
            raise ValueError("No {} mappings for this state: {}".format(source, state))

        mappings = MAPPINGS[source][state]

        self.source = source
        self.state = state

        for mapping in mappings:
            elem = root.findall(mapping["path"])
            if elem:
                if "prop" in mapping:
                    value = elem[0].get(mapping["prop"])
                else:
                    value = elem[0].text

                if value:
                    if mapping["transform"]:
                        value  = mapping["transform"](value)
                    setattr(self, mapping["attr"], value)
                