"""
dmv_lienholder.py - Standard representation of a DMV Lien-Holder record.

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

"""
<textdata>
    <field label="Lien Holder Postion">1</field>
    <field label="Lien Date">20130410</field>
</textdata>
<dataset label="Lien Holder Information" layout="" rec="065140859">
    <dataitem>
        <textdata>
        <field asilist="main" label="Lien Holder Name">HYUNDAI MOTOR FINANCE</field>
        <field asilist="main" label="Lien Holder Number">065140859</field>
        <field label="Street">PO BOX 105299</field>
        <field label="Street (cont)"/>
        <field label="City">ATLANTA</field>
        <field label="State">GA</field>
        <field label="Zip Code">30348-5299</field>
        <field label="Country"/>
        </textdata>
    </dataitem>
</dataset>
"""

class DmvLienHolder(BaseRecord):
    """
    DMV Lien Holder record.
    """
    MAPPINGS = {}
    MAPPINGS["PUBLICDATA"] = {}
    MAPPINGS["PUBLICDATA"]["TX"] = [
        {"path": ".//textdata/field[@label='Lien Holder Position']", "attr": "position"}, #in case they fix spelling
        {"path": ".//textdata/field[@label='Lien Holder Postion']", "attr": "position"}, #in case they fix spelling
        {"path": ".//textdata/field[@label='Lien Date']", "attr": "date"},
        {"path": ".//dataset[@label='Lien Holder Information']/dataitem/textdata/field[@label='Lien Holder Name']", "attr": "name"},
        {"path": ".//dataset[@label='Lien Holder Information']/dataitem/textdata/field[@label='Lien Holder Number']", "attr": "number"},
        {"path": ".//dataset[@label='Lien Holder Information']/dataitem/textdata/field[@label='Street']", "attr": "street"},
        {"path": ".//dataset[@label='Lien Holder Information']/dataitem/textdata/field[@label='Street (cont)']", "attr": "street"},
        {"path": ".//dataset[@label='Lien Holder Information']/dataitem/textdata/field[@label='City']", "attr": "city_state_zip"},
        {"path": ".//dataset[@label='Lien Holder Information']/dataitem/textdata/field[@label='State']", "attr": "city_state_zip"},
        {"path": ".//dataset[@label='Lien Holder Information']/dataitem/textdata/field[@label='Zip Code']", "attr": "city_state_zip"},
        {"path": ".//dataset[@label='Lien Holder Information']/dataitem/textdata/field[@label='Country']", "attr": "country"}
    ]

    def __init__(self):
        """
        Initialize an instance.
        """
        self.position = None
        self.number = None
        self.date = None
        self.name = None
        self.street = None
        self.city_state_zip = None
        self.country = None

    def __str__(self):
        return "({}) {} {} {} {}".format(
            self.position, self.name, self.street, self.city_state_zip, self.country
        )

    # Override from_xml because the XML does not follow the pattern of the other
    # derrived classes.
    def from_xml(self, root, source:str, state:str):
        """
        Parses given XML tree into our standard format.

        Args:
            root (ET): XML element to Process
            source (str): Source database, e.g. "PUBLICDATA"
            state (str): U.S. State, e.g. "TX"
        """
        if source.upper() not in self.MAPPINGS:
            raise ValueError("No mappings for this source: {}".format(source))

        if state.upper() not in self.MAPPINGS[source]:
            raise ValueError("No {} mappings for this state: {}".format(source, state))

        mappings = self.MAPPINGS[source.upper()][state.upper()]

        # ET.dump(root)

        for mapping in mappings:
            path = mapping["path"]
            #print("looking for", path)
            elem = root.findall(path)
            if elem:
                if "prop" in mapping:
                    value = elem[0].get(mapping["prop"])
                else:
                    value = elem[0].text

                #print("\tfound:", value)
                if value:
                    # See if we need to transform the data in any way.
                    if "transform" in mapping and mapping["transform"]:
                        value  = mapping["transform"](value)

                    # If the target attribute already has a value, append this value
                    # to the existing value.
                    if getattr(self, mapping["attr"]):
                        existing_value = getattr(self, mapping["attr"])
                        value = existing_value + " " + value
                    setattr(self, mapping["attr"], value)
            else:
                #print("\tnot found")
                pass
