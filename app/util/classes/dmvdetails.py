"""
dmv.py - Standard representation of a DMV record.

Copyright (c) 2019 by Thomas J. Daley, J.D.
"""
__author__ = "Thomas J. Daley, J.D."
__version__ = "0.0.1"

import xml.etree.ElementTree as ET

from .baserecord import BaseRecord

MAPPINGS = {}
MAPPINGS["PUBLICDATA"] = {}
MAPPINGS["PUBLICDATA"]["TX"] = [
    {"label": "Owner Name", "attr": "owner_name"},
    {"label": "Owner Street", "attr": "owner_street"},
    {"label": "Owner City", "attr": "owner_city"},
    {"label": "Owner State", "attr": "owner_state"},
    {"label": "Owner ZIP Code", "attr": "owner_zip"},
    {"label": "Previous Owner Name", "attr": "prev_owner_name"},
    {"label": "Previous Owner City", "attr": "prev_owner_city"},
    {"label": "Previous Owner State", "attr": "prev_owner_state"},
    {"label": "Renewal Notice Street", "attr": "notice_street"},
    {"label": "Renewal Notice City", "attr": "notice_city"},
    {"label": "Renewal Notice State", "attr": "notice_state"},
    {"label": "Renewal Notice ZIP Code", "attr": "notice_zip"},
    {"label": "License Plate Number", "prop":"formattedplate", "attr": "plate"},
    {"label": "Previous License Plate Number", "prop":"formattedplate", "attr": "prev_plate"},
    {"label": "Title Date", "prop": "formatteddate", "attr": "title_date"},
    {"label": "Vehicle Sold Date", "attr": "sold_date"},
    {"label": "Vehicle Sales Price", "attr": "sold_price"},
    {"label": "Model Year", "attr": "year"},
    {"label": "Make", "attr": "make"},
    {"label": "Model", "attr": "model"},
    {"label": "Model Description", "attr": "model_desc"},
    {"label": "Vehicle Body Type", "attr": "body_type"},
    {"label": "Vehicle Class Code", "attr": "class_code"},
    {"label": "Vehicle Major Color[Color Group]", "attr": "main_color"},
    {"label": "Vehicle Minor Color[Color Group]", "attr": "other_color"},
    {"label": "VIN Number", "prop":"formattedvin", "attr": "vin"}
]

class DmvDetails(BaseRecord):
    """
    Department of Motor Vehicles record.
    """
    def __init__(self):
        """
        Initialize an instance.
        """
        self.owner_city = None
        self.owner_name = None
        self.owner_state = None
        self.owner_street = None
        self.owner_zip = None

        self.prev_owner_city = None
        self.prev_owner_name = None
        self.prev_owner_state = None
        self.prev_owner_street = None
        self.prev_owner_zip = None

        self.notice_owner_city = None
        self.notice_owner_name = None
        self.notice_owner_state = None
        self.notice_owner_street = None
        self.notice_owner_zip = None

        self.plate = None
        self.prev_plate = None
        self.vin = None

        self.title_date = None
        self.sold_date = None
        self.sold_price = None

        self.year = None
        self.make = None
        self.model = None
        self.model_desc = None
        self.body_type = None
        self.class_code = None
        self.main_color = None
        self.other_color = None

    def __str__(self):
        return "{} {} {} {} {}".format(
            self.owner_name, self.owner_street, self.owner_city, self.owner_state, self.owner_zip
        )

    def from_xml(self, root, source:str, state:str):
        """
        Parses given XML tree into our standard format.

        Args:
            root (ET): XML element to Process
            source (str): Source database, e.g. "PUBLICDATA"
            state (str): U.S. State, e.g. "TX"
        """
        if source not in MAPPINGS:
            raise ValueError("No mappings for this source: {}".format(source))

        if state not in MAPPINGS[source]:
            raise ValueError("No {} mappings for this state: {}".format(source, state))

        mappings = MAPPINGS[source][state]

        # ET.dump(root)

        for mapping in mappings:
            path = ".//field[@label='{}']".format(mapping["label"])
            #print("looking for", path)
            elem = root.findall(path)
            if elem:
                if "prop" in mapping:
                    value = elem[0].get(mapping["prop"])
                else:
                    value = elem[0].text

                #print("\tfound:", value)

                if value:
                    setattr(self, mapping["attr"], value)
            else:
                #print("\tnot found")
                pass
                