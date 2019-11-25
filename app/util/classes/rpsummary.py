"""
rpsummary.py - Standard representation of a Real Property summary record.

Copyright (c) 2019 by Thomas J. Daley, J.D.
"""
import hashlib
import re
import xml.etree.ElementTree as ET

from .baserecord import BaseRecord
from util.all_states import StateNameToAbbreviation


def clean_string(s):
    # Remove punctuation
    result = re.sub(r'[.,#!$%^&*;:{}=\-_`~()]', ' ', s)

    # Remove any resulting multiple spaces
    result = re.sub(r'\s{2,}', ' ', result)
    return result


def text_after_colon(s):
    # Strip caption text from beginning of string.
    #
    # Example input: "Owner Address: 812-2 GLAMORGAN AVE SCARBOROUGH ON M1P 2M8 , ,""
    # Example output: "812-2 GLAMORGAN AVE SCARBOROUGH ON M1P 2M8 , ,"
    parts = s.split(":", 2)
    if len(parts) == 2:
        return parts[1].strip()
    return s

MAPPINGS = {}
MAPPINGS["PUBLICDATA"] = {}
MAPPINGS["PUBLICDATA"]["TX"] = {
    "*": [
        {"path": "./disp_fld1", "attr": "owner_name", "transform": clean_string},
        {"path": "./disp_fld2", "attr": "owner_address", "transform": text_after_colon},
        {"path": "./disp_fld3", "attr": "property_address", "transform": text_after_colon},
        {"path": "./source", "attr": "data_source", "transform": None},
        {"path": ".", "prop": "db", "attr": "db", "transform": None},
        {"path": ".", "prop": "ed", "attr": "ed", "transform": None},
        {"path": ".", "prop": "rec", "attr": "rec", "transform": None}
        ]
}
MAPPINGS["PUBLICDATA"]["AR"] = {
    "*": [
        {"path": "./disp_fld1", "attr": "owner_name", "transform": text_after_colon},
        {"path": "./disp_fld2", "attr": "property_id", "transform": text_after_colon},
        {"path": "./disp_fld3", "attr": "parcel_id", "transform": text_after_colon},
        {"path": "./disp_fld4", "attr": "property_address", "transform": text_after_colon},
        {"path": "./source", "attr": "data_source", "transform": None},
        {"path": ".", "prop": "db", "attr": "db", "transform": None},
        {"path": ".", "prop": "ed", "attr": "ed", "transform": None},
        {"path": ".", "prop": "rec", "attr": "rec", "transform": None}
        ],
    "WASHINGTON": [
        {"path": "./disp_fld1", "attr": "owner_name", "transform": None},
        {"path": "./disp_fld2", "attr": "owner_address", "transform": text_after_colon},
        {"path": "./disp_fld3", "attr": "property_address", "transform": text_after_colon},
        {"path": "./source", "attr": "data_source", "transform": None},
        {"path": ".", "prop": "db", "attr": "db", "transform": None},
        {"path": ".", "prop": "ed", "attr": "ed", "transform": None},
        {"path": ".", "prop": "rec", "attr": "rec", "transform": None}
    ]
}


class RealPropertySummary(BaseRecord):
    """
    Real Property record.
    """
    def __init__(self):
        """
        Initialize an instance.
        """
        self.owner_name = None
        self.owner_address = None
        self.property_address = None
        self.property_id = None
        self.parcel_id = None
        self.county = None

        self.zillow = False
        self.street = None
        self.csz = None
        self.latitude = None
        self.longitude = None
        self.zestimate = None
        self.zbranding = None

        self.data_source = None
        self.db = None
        self.ed = None
        self.rec = None
        self.source = None
        self.state = None
        self.hash = None

        self.case_status = "N"  # (I)ncluded, e(X)cluded, or (N)either

    def __str__(self):
        return "Driver name: {} || DOB: {} || Source: {} || State: {}" \
            .format(self.driver_name, self.dob, self.data_source, self.state)

    def key(self)->str:
        """
        Gets the database storage key for this item.
        """
        return "{}:{}.{}.{}".format(self.source, self.db, self.ed, self.rec)

    def from_xml(self, root, source: str, state: str):
        """
        Parses given XML tree into our standard format.

        Args:
            root (ET): XML Root Element for process
            source (str): Source database, e.g. "PUBLICDATA"
            state (str): U.S. State, e.g. "TX"
        """
        if source not in MAPPINGS:
            raise ValueError("No mappings for this source: {}".format(source))

        # Property searches can be nation-wide, so we need to be able to discern the state
        # by looking at the data.
        attribution = root.findall("./source")[0].text  # Expecting, e.g. "Garland County (Arkansas) - blah blah"
        state_regex = r"\(([A-Za-z\s]*)"
        matches = re.findall(state_regex, attribution)
        state = StateNameToAbbreviation[matches[0].upper()]

        county_regex = r"^([A-Za-z\s]*)"
        matches = re.findall(county_regex, attribution)
        county = matches[0].replace(" County", "").strip()

        if state not in MAPPINGS[source]:
            raise ValueError("No {} mappings for this state: {}".format(source, state))

        # The mappings can vary county-by-county within a state. Kill me.
        mappings = MAPPINGS[source][state]
        if county.upper() in mappings:
            mappings = mappings[county.upper()]
        else:
            mappings = mappings["*"]

        self.source = source
        self.state = state
        self.county = county

        for mapping in mappings:
            elem = root.findall(mapping["path"])
            if elem:
                if "prop" in mapping:
                    value = elem[0].get(mapping["prop"])
                else:
                    value = elem[0].text

                if value:
                    if mapping["transform"]:
                        value = mapping["transform"](value)
                    setattr(self, mapping["attr"], value)

        hash_input = "{}{}".format(self.owner_name, self.property_address)
        self.hash = hashlib.md5(hash_input.encode())
