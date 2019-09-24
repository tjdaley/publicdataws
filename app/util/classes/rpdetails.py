"""
rpdetails.py - Standard representation of a Real Property record.

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


def tx_deed_book_id(s):
    if s != "":
        return f"Book {s}"
    return s


def tx_book_page(s):
    if s != "":
        return f"Page {s}"
    return s


def tx_deed_num(s):
    if s != "" and s != "0":
        return f"Instrument # {s}"
    return s


MAPPINGS = {}
MAPPINGS["PUBLICDATA"] = {}
MAPPINGS["PUBLICDATA"]["TX"] = [
    {"label": "Situs Num", "attr": "property_street"},
    {"label": "Situs Street Prefx", "attr": "property_street"},  # in case they fix their spelling
    {"label": "Situs Street Prefix", "attr": "property_street"},
    {"label": "Situs Street", "attr": "property_street"},
    {"label": "Situs Street Sufix", "attr": "property_street"},
    {"label": "Situs Street Suffix", "attr": "property_street"},  # in case they fix their spelling
    {"label": "Situs City", "attr": "property_city"},
    {"label": "Situs State", "attr": "property_state"},
    {"label": "Situs ZIP Code", "attr": "property_zip"},

    {"label": "Prop Id", "attr": "property_id"},
    {"label": "Geo Id", "attr": "parcel_id"},

    {"label": "File As Name", "attr": "owner_name"},
    {"label": "Addr Line1", "attr": "owner_street"},
    {"label": "Addr Line2", "attr": "owner_street"},
    {"label": "Addr Line3", "attr": "owner_street"},
    {"label": "Addr City", "attr": "owner_city"},
    {"label": "Addr State", "attr": "owner_state"},
    {"label": "Addr ZIP Code", "attr": "owner_zip"},

    {"label": "Legal Desc", "attr": "legal_description"},
    {"label": "Deed Type Cd", "attr": "deed_type"},
    {"label": "Deed Dt", "attr": "deed_date"},
    {"label": "Deed Book Id", "attr": "deed_location", "transform": tx_deed_book_id},
    {"label": "Deed Book Page", "attr": "deed_location", "transform": tx_book_page},
    {"label": "Deed Num", "attr": "deed_location", "transform": tx_deed_num},

    {"label": "Yr Blt", "attr": "year_built"},
    {"label": "Living Area", "attr": "living_area"},
    {"label": "Beds", "attr": "beds"},
    {"label": "Baths", "attr": "baths"},
    {"label": "Stories", "attr": "stories"},
    {"label": "Units", "attr": "units"},
    {"label": "Pool", "attr": "pool"},
    {"label": "Legal Acreage", "attr": "acres"},
    {"label": "Zoning", "attr": "zoning"},

    {"label": "Cert Val Yr", "attr": "cad_value_year"},
    {"label": "Cert Market", "attr": "cad_market_value"},
    {"label": "Cert Appraised Val", "attr": "cad_appraised_value"}
]


class RealPropertyDetails(BaseRecord):
    MAPPINGS = MAPPINGS
    """
    Department of Motor Vehicles record.
    """
    def __init__(self, county: str):
        """
        Initialize an instance.
        """
        self.property_street = None
        self.property_city = None
        self.property_state = None
        self.property_county = county
        self.property_zip = None

        self.property_id = None
        self.parcel_id = None

        self.owner_name = None
        self.owner_street = None
        self.owner_city = None
        self.owner_state = None
        self.owner_zip = None

        self.legal_description = None
        self.deed_date = None
        self.deed_type = None
        self.deed_location = None

        self.living_area = 0
        self.year_built = None
        self.beds = 0
        self.baths = 0
        self.stories = 0
        self.units = 0
        self.pool = False
        self.acres = 0
        self.zoning = None

        self.cad_value_year = None
        self.cad_market_value = None
        self.cad_appraised_value = None

        self.zillow = False
        self.street = None
        self.csz = None
        self.latitude = None
        self.longitude = None
        self.zestimate = None
        self.zbranding = None
        self.comps_link = None

    def __str__(self):
        return "{} {} {} {} {}".format(
            self.owner_name, self.property_street, self.property_city, self.property_county, self.property_zip
        )

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

        # The mappings can vary county-by-county within a state. Kill me.
        mappings = MAPPINGS[source][state]
        #if self.property_county.upper() in mappings:
        #    mappings = mappings[self.property_county.upper()]
        #else:
        #    mappings = mappings["*"]

        self.source = source
        self.state = state

        for mapping in mappings:
            path = ".//field[@label='{}']".format(mapping["label"])
            elem = root.findall(path)
            if elem:
                if "prop" in mapping:
                    value = elem[0].get(mapping["prop"])
                else:
                    value = elem[0].text

                if value:
                    # See if we need to transform the data in any way.
                    if "transform" in mapping and mapping["transform"]:
                        value = mapping["transform"](value)

                    # If the target attribute already has a value, append this value
                    # to the existing value.
                    if getattr(self, mapping["attr"]):
                        existing_value = getattr(self, mapping["attr"])
                        value = str(existing_value + " " + value).strip()
                    setattr(self, mapping["attr"], value)
            else:
                # print("\tnot found")
                pass
