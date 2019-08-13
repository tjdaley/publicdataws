"""
dmvsummary.py - Standard representation of a DMV summary record.

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

def transform_tx_year_make_model(s):
    try:
        result = (s.split(":")[1]).strip()
    except Exception:
        result = s

    return result

def transform_tx_plate(s):
    try:
        result = (s.split(":")[1]).strip()
    except Exception:
        result = s

    return result

def transform_co_owner(s):
    try:
        result = (s.split(":")[1]).strip()
    except Exception:
        result = s.copy()
        pass

    if result[-1:] == "/":
        result = result[:-1]
    
    return clean_string(result)

MAPPINGS = {}
MAPPINGS["PUBLICDATA"] = {}
MAPPINGS["PUBLICDATA"]["TX"] = [
    {"path": "./disp_fld1", "attr": "owner_name", "transform": None},
    {"path": "./disp_fld2", "attr": "year_make_model", "transform": transform_tx_year_make_model},
    {"path": "./disp_fld3", "attr": "plate", "transform": transform_tx_plate},
    {"path": "./disp_fld5", "attr": "prev_plate", "transform": None},
    {"path": "./source", "attr": "data_source", "transform": None},
    {"path": ".", "prop": "db", "attr": "db", "transform": None},
    {"path": ".", "prop": "ed", "attr": "ed", "transform": None},
    {"path": ".", "prop": "rec", "attr": "rec", "transform": None}
]
MAPPINGS["PUBLICDATA"]["CO"] = [
    {"path": "./disp_fld1", "attr": "owner_name", "transform": transform_co_owner},
    {"path": "./disp_fld2", "attr": "year_make_model", "transform": transform_tx_year_make_model},
    {"path": "./source", "attr": "data_source", "transform": None},
    {"path": ".", "prop": "db", "attr": "db", "transform": None},
    {"path": ".", "prop": "ed", "attr": "ed", "transform": None},
    {"path": ".", "prop": "rec", "attr": "rec", "transform": None}
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

        self.case_status = "N" # (I)ncluded, e(X)cluded, or (N)either

    def __str__(self):
        return "Owner name: {} || VIN: {} || Year/MakeModel: {} || Plate: {} || Prev Plate: {} || Data Source: {} || Source: {} || State: {}" \
            .format(self.owner_name, self.vin, self.year_make_model, self.plate, self.prev_plate, self.data_source, self.source, self.state)

    def key(self)->str:
        """
        Gets the database storage key for this item.
        """
        return "{}:{}.{}.{}".format(self.source, self.db, self.ed, self.rec)

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
                