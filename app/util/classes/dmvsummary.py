"""
dmvsummary.py - Standard representation of a DMV summary record.

Copyright (c) 2019 by Thomas J. Daley, J.D.
"""
__author__ = "Thomas J. Daley, J.D."
__version__ = "0.0.1"

import xml.etree.ElementTree as ET

from .baserecord import BaseRecord

MAPPINGS = {}
MAPPINGS["PUBLICDATA"] = {}
MAPPINGS["PUBLICDATA"]["TX"] = [
    {"path": "./disp_fld1", "attr": "owner_name"},
    {"path": "./disp_fld2", "attr": "vin"},
    {"path": "./disp_fld3", "attr": "year_make_model"},
    {"path": "./disp_fld4", "attr": "plate"},
    {"path": "./disp_fld5", "attr": "prev_plate"},
    {"path": "./source", "attr": "data_source"},
    {"path": ".", "prop": "db", "attr": "db"},
    {"path": ".", "prop": "ed", "attr": "ed"},
    {"path": ".", "prop": "rec", "attr": "rec"}
]

class DmvSummary(BaseRecord):
    """
    Department of Motor Vehicles record.
    """
    def __init__(self):
        """
        Initialize an instance.
        """
        self.owner_name = None
        self.vin = None
        self.year_make_model = None
        self.plate = None
        self.prev_plate = None
        self.data_source = None
        self.db = None
        self.ed = None
        self.rec = None
        self.source = None
        self.state = None

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
                    setattr(self, mapping["attr"], value)
                