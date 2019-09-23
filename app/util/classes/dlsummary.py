"""
dlsummary.py - Standard representation of a Driver's License summary record.

Copyright (c) 2019 by Thomas J. Daley, J.D.
"""
import hashlib
import re
import xml.etree.ElementTree as ET

from .baserecord import BaseRecord


def clean_string(s):
    # Remove punctuation
    result = re.sub(r'[.,#!$%^&*;:{}=\-_`~()]', ' ', s)

    # Remove any resulting multiple spaces
    result = re.sub(r'\s{2,}', ' ', result)
    return result


def fl_dob(s):
    # Extract DOB from string
    # Example input: "Date of Birth: 19600829"
    # Returns date in MM/DD/YYYY format if the input is formatted as expected,
    # otherwise returns the input string.
    parts = s.split(":")
    if len(parts) != 2:
        return s

    yyyymmdd = parts[1].strip()
    return "{}/{}/{}".format(
        yyyymmdd[4:6],
        yyyymmdd[6:],
        yyyymmdd[0:4]
    )


def fl_dl_number(s):
    # Extract the driver's license number from a string.
    # Example input: "DL Number: P235210603090"
    # Returns the part following the colon.
    parts = s.split(":")
    if len(parts) != 2:
        return s

    return parts[1].strip()


def fl_address(s):
    # Extract and format the address.
    # Example input: "City, State ZIP Code: MIAMI , 33189"
    # Returns, e.g.: "MIAMI, FL 33189"
    parts = s.split(":")
    if len(parts) != 2:
        return s

    parts = parts[1].split(",")
    if len(parts) != 2:
        return s

    city = parts[0].strip()
    zip_code = parts[1].strip()

    return "{}, FL {}".format(city, zip_code)

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
MAPPINGS["PUBLICDATA"]["FL"] = [
    {"path": "./disp_fld1", "attr": "driver_name", "transform": clean_string},
    {"path": "./disp_fld2", "attr": "dob", "transform": fl_dob},
    {"path": "./disp_fld4", "attr": "dl_number", "transform": fl_dl_number},
    {"path": "./disp_fld5", "attr": "address", "transform": fl_address},
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
        self.address = None
        self.dl_number = None

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
                        value = mapping["transform"](value)
                    setattr(self, mapping["attr"], value)

        hash_input = "{}{}".format(self.driver_name, self.dob)
        self.hash = hashlib.md5(hash_input.encode())
