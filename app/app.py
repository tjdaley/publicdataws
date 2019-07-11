"""
webservice.py - Webservice for PublicData

Copyright (c) 2019 by Thomas J. Daley, J.D. All Rights Reserved.
"""
__author__ = "Thomas J. Daley, J.D."
__version__ = "0.0.1"

import argparse
import json
import xml.etree.ElementTree as ET

from util.logger import Logger
from util.publicdata import PublicData

class WebService(object):
    """
    Encapsulates the behavior of a web service for access PublicData.
    """
    def __init__ (self, username:str, password:str):
        """
        Class initializer.
        """
        self.logger = Logger.get_logger(log_name="pdws")
        self.username = username
        self.password = password
        self.api = PublicData()

    def connect(self)->(bool, str):
        """
        Connect to the the PublicData service.

        Args:
            None.
        Returns:
            (bool, str): Where *bool* indicates success or failure and *str* provides an explanatory message.
        """
        return self.api.login(self.username, self.password)

    def tax_records(self, search_terms:str, match_type:str="all", match_scope:str="name", us_state:str="tx", refresh:bool=False)->dict:
        """
        Retrieve tax records throughout the given state.

        Args:
            search_terms (str): Terms to search for in the records
            match_type (str): "all" to match all *search_terms* or "any" to match any *search_terms*.
            match_scope (str): "name" to search by the *name* field or "main" to search in all fields.
            us_state (str): Two-letter state abbreviation to search within.
            refresh (bool): If True, skips the cache and forces a refresh from PublicData. Otherwise returns
                            cached values from that same calendar date, if any.
        Returns:
            (dict): Dictionary of results if successful.
        """
        (success, message, tree) = self.api.tax_records(search_terms, match_type, match_scope, us_state, refresh)
        if not success:
            return {}

        # Convert PublicData XML into a dictionary.
        root = tree.getroot()
        items = root.findall("./results/record")
        for item in items:
            owner = item.find("disp_fld1").text
            address = item.find("disp_fld2").text
            source = item.find("source").text
            print("%-30s - %-75s (%s)" % (owner, address, source))
        return {}

    def dmv_any(self, search_terms):
        return self.__dmv(search_terms, "main")

    def dmv_name(self, search_terms):
        return self.__dmv(search_terms, "name")

    def dmv_plate(self, search_terms):
        return self.__dmv(search_terms, "plate")

    def dmv_vin(self, search_terms):
        return self.__dmv(search_terms, "vin")

    def __dmv(self, search_terms, match_scope):
        (success, message, tree) = self.api.dmv(search_terms, match_scope=match_scope)
        if not success:
            return {}

        # Convert PublicData XML into a dictionary.
        root = tree.getroot()
        cars = root.findall("./results/record")
        tree.write("dmv_{}.xml".format(match_scope))
        for car in cars:
            rec_num = car.get("rec")
            db = car.get("db")
            edition = car.get("ed")
            (status, message, car_details) = self.api.details(db, rec_num, edition)
            # car_details.write("dmv_{}.xml".format(rec_num))
            fields = car_details.findall("./dataset/dataitem/textdata/field")
            details = {}
            for field in fields:
                label = field.get("label").lower()
                if label == "owner name":
                    details["owner"] = field.text
                elif label == "title date":
                    details["purchased"] = field.get("formatteddate")
                elif label == "model year":
                    details["year"] = field.text
                elif label == "make":
                    details["make"] = field.text
                elif label == "model":
                    details["model"] = field.text
                elif label == "vin number":
                    details["vin"] = field.get("formattedvin")
                elif label == "vehicle sales price":
                    details["price"] = field.text
                elif label == "license plate number":
                    details["plate"] = field.text

            print_schedule(amortization_schedule(details), details)
        return {}

    def query(self)->(bool, str):
        """
        Query the PublicData service.

        Args:
            None.
        Returns:
            (bool, str): Where *bool* indicates success or failure and *str* provides an explanatory message.
        """
        return self.api.document()

def print_schedule(schedule:list, details:dict):
    print("-"*41)
    print("%-41s" % "A M O R T I Z A T I O N   S C H E D U L E")
    print("Vehicle: %s %s %s" % (details["year"], details["make"], details["model"]))
    print("VIN    : %s" % details["vin"])
    print("Titled : %s" % details["owner"])
    print("-"*41)
    print("%4s  %-11s  %-11s  %-11s" % ("Year", "Begin", "Deprec.", "End"))
    for line_item in schedule:
        print("%-4s  %9.2f  %9.2f  %9.2f" % (line_item["year"], line_item["begin_value"], line_item["depreciation"], line_item["end_value"]))

def amortization_schedule(details:dict)->list:
    year = int(details["year"])
    useful_life = 15 #years
    sum_of_years = sum(year for year in range(1, useful_life+1))
    original_value = float(details["price"])/100.00
    start_value = float(details["price"])/100.00
    schedule = []

    for amort_year in range(useful_life, 0, -1):
        depreciation = float(amort_year / sum_of_years) * original_value * -1
        end_value = start_value + depreciation
        year += 1
        schedule.append({"year": str(year), "begin_value": start_value, "depreciation": depreciation, "end_value": end_value})
        start_value = end_value

    return schedule

def main(args:{}):
    webservice = WebService(args.username, args.password)
    (success, message) = webservice.connect()
    if success:
        webservice.tax_records("785 MeadowView", match_scope="main")
        print("-----M A I N------------------------------------------------------")
        webservice.dmv_any("3011 Chukar McKinney")
        print("-----P L A T E----------------------------------------------------")
        webservice.dmv_plate("DXZ3906")
        print("-----V I N--------------------------------------------------------")
        webservice.dmv_vin("2C3KA63HX8H139624")

    else:
        print("Error logging in:", message)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Webservice for PublicData")
    parser.add_argument("--username", "-u", required=True, help="Username for logging into the PublicData service.")
    parser.add_argument("--password", "-p", required=True, help="Password for logging into the PublicData service.")
    args = parser.parse_args()
    main(args)
