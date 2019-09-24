"""
dmv.py - Standard representation of a DMV record.

Copyright (c) 2019 by Thomas J. Daley, J.D.
"""
import re
import xml.etree.ElementTree as ET

from .baserecord import BaseRecord


def clean_string(s):
    # Remove punctuation
    result = re.sub(r'[.,#!$%^&*;:{}=\-_`~()]', ' ', s)

    # Remove any resulting multiple spaces
    result = re.sub(r'\s{2,}', ' ', result)
    return result


def money(s):
    try:
        result = float(s) / 100
    except Exception as e:
        print("Error converting", s, str(e))
        result = s

    return result

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
    {"label": "License Plate Number", "prop": "formattedplate", "attr": "plate"},
    {"label": "Previous License Plate Number", "prop": "formattedplate", "attr": "prev_plate"},
    {"label": "Title Date", "prop": "formatteddate", "attr": "title_date"},
    {"label": "Vehicle Sold Date", "attr": "sold_date"},
    {"label": "Vehicle Sales Price", "attr": "sold_price", "transform": money},
    {"label": "Model Year", "attr": "year"},
    {"label": "Make", "attr": "make"},
    {"label": "Model", "attr": "model"},
    {"label": "Model Description", "attr": "model_desc"},
    {"label": "Vehicle Body Type", "attr": "body_type"},
    {"label": "Vehicle Class Code", "attr": "class_code"},
    {"label": "Vehicle Major Color[Color Group]", "attr": "main_color"},
    {"label": "Vehicle Minor Color[Color Group]", "attr": "other_color"},
    {"label": "VIN Number", "prop": "formattedvin", "attr": "vin"}
]
MAPPINGS["PUBLICDATA"]["CO"] = [
    {"label": "Owner 1", "attr": "owner_name", "transform": clean_string},
    {"label": "Owner 2", "attr": "owner_name", "transform": clean_string},
    {"label": "Owner 3", "attr": "owner_name", "transform": clean_string},
    {"label": "Legal Address", "attr": "owner_street"},
    {"label": "Legal City", "attr": "owner_city"},
    {"label": "Legal State", "attr": "owner_state"},
    {"label": "Legal ZIP Code", "attr": "owner_zip"},
    {"label": "Mail Address", "attr": "notice_street"},
    {"label": "Mail City", "attr": "notice_city"},
    {"label": "Mail State", "attr": "notice_state"},
    {"label": "Mail ZIP Code", "attr": "notice_zip"},
    {"label": "Lic. Plate", "prop": "formattedplate", "attr": "plate"},
    {"label": "Previous License Plate", "prop": "formattedplate", "attr": "prev_plate"},
    {"label": "Tran. Date", "prop": "formatteddate", "attr": "title_date"},
    {"label": "Purchase Date", "prop": "formatteddate", "attr": "sold_date"},
    {"label": "Purchase Price", "attr": "sold_price"},
    {"label": "Vehicle Year", "attr": "year"},
    {"label": "Make", "attr": "make", "transform": money},
    {"label": "Model", "attr": "model"},
    {"label": "Model Description", "attr": "model_desc"},
    {"label": "Title Vehicle Type", "attr": "body_type"},
    {"label": "Own. Tax Class", "attr": "class_code"},
    {"label": "VIN", "attr": "vin"}
]


class DmvDetails(BaseRecord):
    MAPPINGS = MAPPINGS
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

        self.notice_city = None
        self.notice_name = None
        self.notice_state = None
        self.notice_street = None
        self.notice_zip = None

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

        self.lien_holders = []
        self.amortization_schedule = None
        self.amortization_message = None

    def __str__(self):
        return "{} {} {} {} {}".format(
            self.owner_name, self.owner_street, self.owner_city, self.owner_state, self.owner_zip
        )
