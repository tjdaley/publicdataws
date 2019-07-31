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
from util.zillow import Zillow
from util.classes.dmvdetails import DmvDetails

class WebService(object):
    """
    Encapsulates the behavior of a web service for accessing PublicData.
    """
    def __init__ (self, zillow_id:str):
        """
        Class initializer.
        """
        self.logger = Logger.get_logger(log_name="pdws")
        self.public_data = PublicData()
        self.zillow = Zillow(zillow_id)

    def tax_records(self, credentials:dict, search_terms:str, match_type:str="all", match_scope:str="name", us_state:str="tx", get_zillow:bool=True, refresh:bool=False)->list:
        """
        Retrieve tax records throughout the given state.

        Args:
            credentials (dict): username and password
            search_terms (str): Terms to search for in the records
            match_type (str): "all" to match all *search_terms* or "any" to match any *search_terms*.
            match_scope (str): "name" to search by the *name* field or "main" to search in all fields.
            us_state (str): Two-letter state abbreviation to search within.
            get_zillow (bool): Get ZILLOW results?
            refresh (bool): If True, skips the cache and forces a refresh from PublicData. Otherwise returns
                            cached values from that same calendar date, if any.
        Returns:
            (dict): Dictionary of results if successful.
        """
        (success, message, tree) = self.public_data.tax_records(credentials, search_terms, match_type, match_scope, us_state, refresh)
        if not success:
            self.logger.warn(message)
            return []
        
        # Convert PublicData XML into a list.
        results = []
        root = tree.getroot()
        items = root.findall("./results/record")
        self.logger.debug("Retrieved %d tax records.", len(items))

        for item in items:
            owner = item.find("disp_fld1").text
            address = item.find("disp_fld2").text
            (street, csz) = address.split(",", 1)
            street = street.split(":", 1)[0]
            source = item.find("source").text
            parcel = {"owner": owner, "street": street.strip(), "csz": csz.strip(), "source":source, "zillow": False}
            results.append(parcel)

        if get_zillow:
            results = self.zillow_data(results)

        return results

    def zillow_data(self, properties:list)->list:
        results = []
        for parcel in properties:
            (success, message, tree) = self.zillow.search(parcel["street"], parcel["csz"])
            if not success:
                self.logger.error("Error retrieving ZILLOW data for %s, %s: %s", parcel["street"], parcel["csz"], message)
                parcel["zillow"] = False
                results.append(parcel)
                continue
            
            root = tree.getroot()
            address = root.find("./response/results/result/address")
            parcel["zillow"] = True
            parcel["street"] = address.find("street").text
            parcel["csz"] = "{}, {} {}".format(address.find("city").text, address.find("state").text, address.find("zipcode").text)
            parcel["latitide"] = address.find("latitude").text
            parcel["longitude"] = address.find("longitude").text
            parcel["zestimate"] = float(root.find("./response/results/result/zestimate/amount").text)
            details_link = root.find("./response/results/result/links/homedetails").text
            parcel["zbranding"] = '<a href="{}">See more details for {} on Zillow.</a>'.format(details_link, parcel["street"])
            results.append(parcel)
        return results

    def dmv_any(self, credentials, search_terms, us_state="tx"):
        return self.__dmv(credentials, search_terms, "main", us_state)

    def dmv_name(self, credentials, search_terms, us_state="tx"):
        return self.__dmv(credentials, search_terms, "name", us_state)

    def dmv_plate(self, credentials, search_terms, us_state="tx"):
        return self.__dmv(credentials, search_terms, "plate", us_state)

    def dmv_vin(self, credentials, search_terms, us_state="tx"):
        return self.__dmv(credentials, search_terms, "vin", us_state)

    def __dmv(self, credentials, search_terms, match_scope, us_state="tx"):
        """
        Search DMV records.

        TODO: Refactor this method out of the class.

        Args:
            search_terms (str): Text to look for.
            match_scope (str): One of main (search all fields); name (search owner name field);
                plate (search for license plate); or vin (search for VIN)

        Returns:
            (success, message, car_summaries): Where success is a bool indicating success or failure;
                message is an explanation of any error encountered; and car_summaries is a list
                of DmvSummary instances.
        """
        return self.public_data.dmv(
            credentials=credentials,
            search_terms=search_terms,
            match_scope=match_scope,
            us_state=us_state)

    def drivers_license(self, credentials:dict, search_terms:str, search_scope:str, us_state:str):
        return self.public_data.drivers_license(
            credentials,
            search_terms=search_terms,
            match_scope=search_scope,
            us_state=us_state)

    def driver_details(self, credentials:dict, db:str, ed:str, rec:str, us_state:str):
        return self.public_data.driver_details(credentials, db, ed, rec, us_state)

    def dmv_details(self, credentials:dict, db:str, ed:str, rec:str, us_state:str):
        """
        Retrieve Details for this record from PublicData

        Args:
            credentials (dict): username and password
            db (str): Database name
            ed (str): Database edition
            rec (str): Record ID
            us_state (str): Two-letter state abbreviation for this record
        Returns:
            (success, message, object)
        """
        return self.public_data.dmv_details(credentials, db, ed, rec, us_state)

    def amortization_schedule(self, details:dict, normal_useful_life:int=15)->(list, str):
        """
        Compute an amortization schedule for this asset.
        This method applies a sum-of-the-years-digits accelerate depreciation
        to recognize that assets depreciate more rapidly in their earlier life.

        Args:
            details (dict): Details about the asset to be depreciated. Must contain the following keys:
                "year" = Model year of the vehicle or manufactured year of any other asset (YYYY).
                "sold_price" = Price the car was sold for, in hundredths of a dollar (pennies)
                "title_date" = Date the car was first titled to the current owner (YYYYMMDD)
                "sold_date" = Date the car was sold to the current owner (YYYYMMDD). Not required if title_date provided.
            normal_useful_life (int): Number of years of normal useful life (not remaining useful life.)

        Returns:
            (list): List of dicts containing the depreciation record for one year.
            (str): A message explaining the outcome of this method.
        """
        try:
            year = int(details["year"])
        except KeyError as e:
            return ([], "Cannot depreciate an asset with no model year (1).")
        except AttributeError as e:
            return ([], "Cannot depreciate an asset wtih no model year (2).")
        except ValueError as e:
            return ([], "Invalid year: {}".format(str(e)))
        
        try:
            original_value = float(details["sold_price"])/100.00
            start_value = float(details["sold_price"])/100.00
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
            purchased_year = int(details["title_date"][:4])
        except Exception as e:
            print(str(e))
            purchased_year = year
            message = "Unable to parse purchase date of '{}'. Used '{}' instead" \
                    .format(details["sold_date"], year)

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


def print_schedule(schedule:list, message:str, details:DmvDetails):
    print("\n", "-"*41, sep="")
    print("%-41s" % "A M O R T I Z A T I O N   S C H E D U L E\n")
    print(message)

    try:
        print("Vehicle: %s %s %s" % (details.year, details.make, details.model))
    except Exception as e:
        print("Incomplete details: {}".format(str(e)))
        print(details)
        return

    if details.title_date:
        purch_year = details.title_date[0:4]
        purch_month = details.title_date[4:6]
        purch_day = details.title_date[6:8]
        purch_date = "{}/{}/{}".format(purch_month, purch_day, purch_year)
    else:
        purch_date = "(Unknown)"
    print("VIN    : %s" % (details.vin))
    print("Purch  : %s for $%8.2f" % (purch_date, float(details.sold_price)/100.00))
    print("Titled : %s" % details.owner_name)
    print("-"*41)
    if schedule:
        print("%4s  %-11s  %-11s  %-11s" % ("Year", "Begin", "Deprec.", "End"))
    for line_item in schedule:
        print("%-4s  %9.2f  %9.2f  %9.2f" % (line_item["year"], line_item["begin_value"], line_item["depreciation"], line_item["end_value"]))


def main(args:{}):
    credentials = {"username": args.username, "password": args.password}
    webservice = WebService(args.zillowid)
    """
    records = webservice.tax_records(args.search, match_scope="main")
    for record in records:
        if record["zillow"]:
            message = "{}\n{}\n{}\nZEstimate: {}\n{}\n({})\n".format(
                record["owner"], record["street"], record["csz"], record["zestimate"], record["zbranding"], record["source"])
        else:
            message = "{}\n{}\n{}\n({})\n".format(
                record["owner"], record["street"], record["csz"], record["source"])
        print(message)
    """
    #print("-----M A I N------------------------------------------------------")
    #webservice.dmv_any(args.search)
    #print("-----P L A T E----------------------------------------------------")
    #webservice.dmv_plate("DXZ3906")
    print("-----V I N--------------------------------------------------------")
    (success, message, cars) = webservice.dmv_vin(credentials, "2C3KA63HX8H139624")
    if success:
        for car in cars:
            (d_success, d_message, details) = webservice.dmv_details(credentials, car.db, car.ed, car.rec, car.state)
            detail_dict = {}
            detail_dict["year"] = details.year
            detail_dict["sold_price"] = details.sold_price
            detail_dict["title_date"] = details.title_date
            detail_dict["sold_date"] = details.sold_date
            (schedule, message) = webservice.amortization_schedule(detail_dict)
            print_schedule(schedule, message, details)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Webservice for PublicData")
    parser.add_argument("--username", "-u", help="Username for logging into the PublicData service.")
    parser.add_argument("--password", "-p", help="Password for logging into the PublicData service.")
    parser.add_argument("--zillowid", "-z", help="Zillow API credential from https://www.zillow.com/howto/api/APIOverview.htm")
    parser.add_argument("--search", "-s", help="Search term")
    args = parser.parse_args()
    main(args)
