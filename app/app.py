"""
webservice.py - Webservice for PublicData

Copyright (c) 2019 by Thomas J. Daley, J.D. All Rights Reserved.
"""
__author__ = "Thomas J. Daley, J.D."
__version__ = "0.0.1"

import argparse
from datetime import datetime
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

            (schedule, message) = amortization_schedule(details)
            print_schedule(schedule, message, details)
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

def print_schedule(schedule:list, message:str, details:dict):
    print("\n", "-"*41, sep="")
    print("%-41s" % "A M O R T I Z A T I O N   S C H E D U L E\n")
    print(message)

    try:
        print("Vehicle: %s %s %s" % (details["year"], details["make"], details["model"]))
    except Exception as e:
        print("Incomplete details: {}".format(str(e)))
        print(details)
        return

    if details["purchased"]:
        purch_year = details["purchased"][0:4]
        purch_month = details["purchased"][4:6]
        purch_day = details["purchased"][6:8]
        purch_date = "{}/{}/{}".format(purch_month, purch_day, purch_year)
    else:
        purch_date = "(Unknown)"
    print("VIN    : %s" % (details["vin"]))
    print("Purch  : %s  for $%8.2f" % (purch_date, float(details["price"])/100.00))
    print("Titled : %s" % details["owner"])
    print("-"*41)
    if schedule:
        print("%4s  %-11s  %-11s  %-11s" % ("Year", "Begin", "Deprec.", "End"))
    for line_item in schedule:
        print("%-4s  %9.2f  %9.2f  %9.2f" % (line_item["year"], line_item["begin_value"], line_item["depreciation"], line_item["end_value"]))

def amortization_schedule(details:dict, normal_useful_life:int=15)->(list, str):
    """
    Compute an amortization schedule for this asset.
    This method applies a sum-of-the-years-digits accelerate depreciation
    to recognize that assets depreciate more rapidly in their earlier life.

    Args:
        details (dict): Details about the asset to be depreciated. Must have at least
                        "year"........The year the asset was manufactured.
                        "price".......The purchase price, in hundredths of dollars.
                        "purchased"...The date the asset was purchased (YYYYMMDD)
        normal_useful_life (int): Number of years of normal useful life (not remaining useful life.)

    Returns:
        (list): List of dicts containing the depreciation record for one year.
        (str): A message explaining the outcome of this method.
    """
    try:
        year = int(details["year"])
    except KeyError as e:
        return ([], "Cannot depreciate an asset with no model year.")
    
    try:
        original_value = float(details["price"])/100.00
        start_value = float(details["price"])/100.00
    except KeyError as e:
        return([], "Cannot depreciate an asset with no purchase price.")

    this_year = int(datetime.now().strftime("%Y"))
    schedule = []
    message = ""

    # Cannot depreciate something that has no starting value
    if original_value == 0.00:
        return schedule, "Cannot depreciate an asset having no initial value."

    # What year was this asset purchased?
    try:
        purchased_year = int(details["purchased"][:4])
    except Exception as e:
        print(str(e))
        purchased_year = year
        message = "Unable to parse purchase date of '{}'. Used '{}' instead" \
                  .format(details["purchased"], year)

    # If the asset's purchase year is less than the model year (frequently happens with
    # motor vehicles), use the purchase year as the base year.
    if purchased_year == 0:
        purchased_year = year
    elif purchased_year < year:
        year = purchased_year

    # If asset has no remaining useful life, we're done.
    if (purchased_year > year + normal_useful_life) or (this_year > year + normal_useful_life):
        message = "Asset has no significant remaining value due to its age."
        return (schedule, message)

    # If asset was purchased *after* its model year (i.e. used), reduce it's
    # remaining useful life accordingly.
    if purchased_year > year:
        useful_life = normal_useful_life - (purchased_year - year)
        message = "Normal useful life of {} years reduced to remaining useful life of {} years." \
                  .format(normal_useful_life, useful_life)
        year = purchased_year
    else:
        useful_life = normal_useful_life

    sum_of_years = sum(year for year in range(1, useful_life+1))

    for amort_year in range(useful_life, 0, -1):
        depreciation = float(amort_year / sum_of_years) * original_value * -1
        end_value = start_value + depreciation
        schedule.append({"year": str(year), "begin_value": start_value, "depreciation": depreciation, "end_value": end_value})
        if year == this_year:
            message = (message + " Current FMV = $%9.2f." % end_value).strip()
        year += 1
        start_value = end_value

    return (schedule, message)

def main(args:{}):
    webservice = WebService(args.username, args.password)
    (success, message) = webservice.connect()
    if success:
        #webservice.tax_records("785 MeadowView", match_scope="main")
        #print("-----M A I N------------------------------------------------------")
        webservice.dmv_any(args.search)
        #print("-----P L A T E----------------------------------------------------")
        #webservice.dmv_plate("DXZ3906")
        #print("-----V I N--------------------------------------------------------")
        #webservice.dmv_vin("2C3KA63HX8H139624")

    else:
        print("Error logging in:", message)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Webservice for PublicData")
    parser.add_argument("--username", "-u", help="Username for logging into the PublicData service.")
    parser.add_argument("--password", "-p", help="Password for logging into the PublicData service.")
    parser.add_argument("--search", "-s", help="Search term")
    args = parser.parse_args()
    main(args)
