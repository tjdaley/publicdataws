"""
publicdata.py - Python API for Public Data searches.

Based on documentation available at: http://www.publicdata.com/pdapidocs/index.php

Copyright (c) 2019 by Thomas J. Daley, J.D. All Rights Reserved.
"""
import base64
from datetime import datetime
import os
import re
import requests
import xml.etree.ElementTree as ET
import xml

from .database import Database
from .logger import Logger
from .all_states import StateAbbreviations

from .classes.dmvdetails import DmvDetails
from .classes.dmv_lienholder import DmvLienHolder
from .classes.dmvsummary import DmvSummary
from .classes.dlsummary import DlSummary
from .classes.dldetails import DlDetails
from .classes.rpdetails import RealPropertyDetails
from .classes.rpsummary import RealPropertySummary

LOGIN_URL = "https://login.publicdata.com/pdmain.php/logon/checkAccess?disp=XML&login_id={}&password={}"
SOURCE = "PUBLICDATA"
MAX_PAGES = 10  # Most number of pages that we'll pull before telling user the request was too broad


class PublicData(object):
    """
    Encapsulates an interface into PublicData's web site via Python.
    """
    def __init__(self):
        """
        Class Initializer.
        """
        self.logger = Logger.get_logger(log_name="pdws.api")
        self.daykey_cache = {}
        self.login_date = None
        self.hierarchy = []

        self.database = None
        self.connect_db()

    def connect_db(self):
        """
        Connect to the datastore.

        Args:
            None.

        Returns:
            (bool): Whether connection as successful.
        """

        # If we've never connected, connect now.
        if self.database is None:
            database = Database()
            success = database.connect()
            if success:
                self.database = database
            return success

        # See if existing connection is OK.
        try:
            self.database.test_connection()
            success = True
        except Exception as e:
            self.logger.error("Error testing database connection: %s", e)
            self.database = None
            database = Database()
            success = database.connect()

        return success

    def load_xml(self, url: str, refresh=False, filename: str=None)->(bool, str, object):
        """
        Load XML either from a cached file or a URL. If the cache file exists, we'll load from there.
        If the cache file does not exist, we'll load from the URL.

        Args:
            url (str): URL to load from if cache file does not exist.
            refresh (bool): True to by-pass cached results and force a query to the server.
            filename (str): Name of the cache file to try to load. If omitted (as it normally should be),
                            cacheing is done through the database.

        Returns:
            (bool, str, object): The *bool* indicates success or failure.
                                 The *str* provides a diagnostic message.
                                 The *object* is an ET tree, if successful otherwise NoneType.
        """
        # See if the cache file exists. If so, it is not necessary
        # to query the URL - we will just parse the contents of the file.
        try:
            if filename and os.path.exists(filename) and not refresh:
                self.logger.debug("Loading from file: %s", filename)
                tree = ET.parse(filename)
                return (True, "OK", tree)

            if self.database and not refresh:
                response = self.database.check_cache(SOURCE, url)
                if response:
                    self.logger.debug("Loading from cache.")
                    return (True, "OK", response)

            self.logger.debug("Loading from URL: %s", url)

            # Retrieve response from server
            response = requests.get(url, allow_redirects=False)

            # Convert response from stream of bytes to string
            content = response.content.decode()

            # Deserialize response to XML element tree
            tree = ET.ElementTree(ET.fromstring(content))

            # See if we got an error response.
            root = tree.getroot()
            if root.get("type").lower() == "error":
                message = error_message(root)
                return (False, message, tree)

            # All looks ok from a 30,000-foot level.
            # Cache the response and return it to our caller.
            if filename:
                open(filename, "w").write(content)
            elif self.database:
                self.database.insert_cache(source=SOURCE, query=url, result=tree)
            else:
                self.logger.warn("Unable to cache search result. Is the database down?")

            return (True, "OK", tree)
        except xml.etree.ElementTree.ParseError as e:
            self.logger.error("Error parsing XML: %s", e)
            self.logger.error("Failed XML: %s", content)
            return (False, str(e), None)
        except Exception as e:
            self.logger.error("Error reading cache or loading from URL: %s", e)
            self.logger.error("Failed URL: %s", url)
            self.logger.exception(e)
            return (False, str(e), None)

        return (False, "Programmer Error", None)

    def login(self, username: str, password: str)->(bool, str, dict):
        """
        Attempt to login to the PublicData servers.

        Args:
            username (str): The login_id to be used.
            password (str): The password to be used.

        Returns:
            (bool, str, dict): Where the bool incates success ("True") or failure; str is
                         a diagnostic message; and dict is the data we need for this user.
        """
        try:
            # Generate name of today's login response.
            xml_file_name = "{}-{}-login.xml".format(today_yyyymmdd(), username)

            # Return cached result if we've already logged in today.
            if xml_file_name in self.daykey_cache:
                return (True, "OK", self.daykey_cache[xml_file_name])

            #####
            # First time this user has logged in, so connect to the server and try to login.
            #####

            # Format URL
            url = LOGIN_URL.format(username, password)
            # Load XML tree from file or URL
            (success, message, tree) = self.load_xml(url, filename=xml_file_name)

            if not success:
                return (success, message, {})

            # We have our XML tree, now process it.
            root = tree.getroot()
            self.login_date = today_yyyymmdd()

            child = root.find("user")
            sid = child.find("id").text

            # If we get a NoneType *id*, the login failed.
            if not sid:
                child = root.find("pdheaders")
                message = child.find("pdheader1").text
                return (False, message, {})

            # Successful login . . . keep going.
            session_id = child.find("sessionid").text
            login_id = child.find("dlnumber").text

            child = root.find("servers")
            search_server = child.find("searchserver").text
            login_server = child.find("loginserver").text
            main_server = child.find("mainserver").text

            # Update Day Key Cache
            keys = {
                "session_id": session_id,
                "login_id": login_id,
                "search_server": search_server,
                "login_server": login_server,
                "main_server": main_server,
                "id": sid
                }
            self.daykey_cache[xml_file_name] = keys
            # TODO: Check our remaining searches and post a warning if low and a panic message is depleted.

            return (True, "OK", keys)
        except Exception as e:
            self.logger.error("Error connecting to %s: %s", LOGIN_URL, e)
            self.logger.exception(e)
            message = str(e)

        return (False, message)

    def tax_records(self, credentials: dict, search_terms: str, match_type: str="all", match_scope: str="name", us_state: str="tx", refresh: bool=False)->(bool, str, object):
        """
        Search for Tax Records by state. Results are cached for one day (until midnight, not necessarily 24 hours).

        Args:
            credentials (dict): Contains username and password for accessing the database
            search_terms (str): Terms to search for in the records
            match_type (str): "all" to match all *search_terms* or "any" to match any *search_terms*.
            match_scope (str): "name" to search by the *name* field or "main" to search in all fields.
            us_state (str): Two-letter state abbreviation to search within.
            refresh (bool): If True, skips the cache and forces a refresh from PublicData. Otherwise returns
                            cached values from that same calendar date, if any.

        Returns:
            (bool, str, object): The *bool* indicates success or failure.
                                 The *str* provides a diagnostic message.
                                 The *object* is an ET tree, if successful otherwise NoneType.
        """
        try:
            db_name = "grp_cad_tx_advanced_" + match_scope
            return self.search(credentials, db_name, search_terms, match_type, match_scope, us_state, refresh)
        except Exception as e:
            self.logger.error("Error retrieving from %s: %s")
            self.logger.exception(e)
            message = str(e)

        return (False, message, None)

    def drivers_license(
        self,
        credentials: dict,
        search_terms: str,
        exemption: str=None,
        match_type: str="all",
        match_scope: str="main",
        us_state: str="tx",
        refresh: bool=False
    )->(bool, str, list):
        """
        Search Driver's License records.

        Args:
            credentials (dict): username and password for Public Data service.
            search_terms (str): The text being searched (DOB is YYYYMMDD)
            match_type (str): "all" or "any" depending on how to want to search for each word in search_terms
            match_scope (str): Type of search ("main", "name", "dob", "dlnum")
            us_state (str): U.S. state to search. "tx" and "fl" is the only legal values
            refresh (bool): True to force a load from the remote URL; False to use recently cached result
            exemption (str): Exemption code to use for this search. Illegal to search without an exemption

        Returns:
            (
                (bool): Success?
                (str): Message explaining any error that's reported.
                (list): List of DmvSummary instances
            )
        """
        valid_states = ['tx', 'fl']
        if us_state.lower() not in valid_states:
            message = "Cannot search for driver's license in {}. Can only search {}.".format(us_state, ", ".join(valid_states))
            return (False, message, [])

        if match_type.lower() not in ['all', 'any']:
            return (False, "Invalid match type: {}. Must be either 'any' or 'all'.".format(match_type), [])

        valid_scopes = ['main', 'name', 'dob', 'dlnum']
        if match_scope.lower() not in valid_scopes:
            message = "Invalid match scope: {}. Must be one of: {}".format(match_scope, ", ".join(valid_scopes))
            return (False, message, [])

        # Slight variation in database name, depending on which state
        if us_state == "tx":
            db_ending = "_dbs"
            exemption = exemption or "tacDMV=DPPATX-01"
        else:
            db_ending = ""
            exemption = exemption or "tacDMV=DPPAFL-03"

        db_name = "{}dl{}|{}".format(us_state, db_ending, match_scope)
        summaries = []

        # Loop through paged results.
        more_pages = True
        searchmoreid = None
        max_pages = MAX_PAGES  # Not going to pull more than this many pages, no matter how many there are.
        while more_pages and max_pages > 0:
            (success, message, tree) = self.search(credentials,
                                                   db_name=db_name,
                                                   search_terms=search_terms,
                                                   match_scope=match_scope,
                                                   exemption=exemption,
                                                   searchmoreid=searchmoreid)

            # If we encoutered a problem, return whatever we already accumluated, if anything
            if not success:
                return (False, message, summaries)

            # Successful search (meaning no errors)
            # Append results to our list of summaries are accumulating
            max_pages -= 1
            root = tree.getroot()
            drivers = root.findall("./results/record")
            for driver in drivers:
                dl_summary = DlSummary()
                dl_summary.from_xml(driver, SOURCE, us_state.upper())
                summaries.append(dl_summary)

            # See if there are other pages of results to process.
            try:
                more_pages = (root.findall("./results")[0].get("ismore")).lower() == "true"
            except IndexError:
                more_pages = False

            # If there are more, get reference to the next page id.
            if more_pages:
                searchmoreid = root.findall("./results")[0].get("searchmoreid")

        return (success, message, summaries)

    def driver_details(self, credentials, db, ed, rec, us_state, exemption: str=None, refresh: bool=False)->(bool, str, object):
        exemption = exemption or {
            'co': "tacDMV=DPPA-01",
            'fl': "tacDMV=DPPAFL-03",
            'ms': "tacDMV=DPPA-01",
            'tx': "tacDMV=DPPATX-01",
            'wv': "tacDMV=DPPA-01",
            'wi': "tacDMV=DPPA-01"
            }[us_state.lower()]
        (success, message, tree) = self.details(credentials, db, rec, ed, exemption, refresh)
        details = None
        if success:
            root = tree.getroot()
            fields = root.findall("./dataset/dataitem/textdata")
            details = DlDetails()
            details.from_xml(fields[0], SOURCE, us_state)
            details.state = us_state

        return (success, message, details)

    def dmv(
        self,
        credentials: dict,
        search_terms: str,
        exemption: str=None,
        match_type: str="all",
        match_scope: str="name",
        us_state: str="tx",
        refresh: bool=False
    )->(bool, str, list):
        """
        Search DMV records.

        Args:
            credentials (dict): username and password for Public Data service.
            search_terms (str): The text being searched
            match_type (str): "all" or "any" depending on how to want to search for each word in search_terms
            match_scope (str): Type of search: "main", "name", "plate", "vin"
            us_state (str): U.S. state to search. "tx" is the only useful value
            refresh (bool): True to force a load from the remote URL; False to use recently cached result
            exemption (str): Exemption code to use for this search. Illegal to search without an exemption

        Returns:
            (
                (bool): Success?
                (str): Message explaining any error that's reported.
                (list): List of DmvSummary instances
            )
        """
        valid_states = ['co', 'fl', 'ms', 'tx', 'wv', 'wi']
        if us_state.lower() not in valid_states:
            message = "Cannot search for driver's license in {}. Can only search {}.".format(us_state, ", ".join(valid_states))
            return (False, message, [])

        if match_type.lower() not in ['all', 'any']:
            return (False, "Invalid match type: {}. Must be either 'any' or 'all'.".format(match_type), [])

        valid_scopes = ['main', 'name', 'plate', 'vin']
        if match_scope.lower() not in valid_scopes:
            message = "Invalid match scope: {}. Must be one of: {}".format(match_scope, ", ".join(valid_scopes))
            return (False, message, [])

        exemption = exemption or {
            'co': "tacDMV=DPPA-01",
            'fl': "tacDMV=DPPAFL-03",
            'ms': "tacDMV=DPPA-01",
            'tx': "tacDMV=DPPATX-01",
            'wv': "tacDMV=DPPA-01",
            'wi': "tacDMV=DPPA-01"
            }[us_state.lower()]

        # Slight variation in database name, depending on which state
        if us_state == "wi":
            db_name = "grp_dmv_wi_advanced_main"
        else:
            db_name = "{}dmv|{}".format(us_state, match_scope)
        summaries = []

        # Loop through paged results.
        more_pages = True
        searchmoreid = None
        max_pages = MAX_PAGES  # Not going to pull more than this many pages, no matter how many there are.
        while more_pages and max_pages > 0:
            (success, message, tree) = self.search(credentials,
                                                   db_name=db_name,
                                                   search_terms=search_terms,
                                                   match_scope=match_scope,
                                                   exemption=exemption,
                                                   searchmoreid=searchmoreid)

            # If we encoutered a problem, return whatever we already accumluated, if anything
            if not success:
                return (False, message, summaries)

            # Successful search (meaning no errors)
            # Append results to our list of summaries are accumulating
            max_pages -= 1
            root = tree.getroot()
            cars = root.findall("./results/record")
            for car in cars:
                dmv_summary = DmvSummary()
                dmv_summary.from_xml(car, SOURCE, us_state.upper())
                summaries.append(dmv_summary)

            # See if there are other pages of results to process.
            # print("IS MORE?",(root.findall("./results")[0].get("ismore")).lower())
            try:
                more_pages = (root.findall("./results")[0].get("ismore")).lower() == "true"
            except IndexError:
                more_pages = False

            # If there are more, get reference to the next page id.
            if more_pages:
                searchmoreid = root.findall("./results")[0].get("searchmoreid")

        return (success, message, summaries)

    def dmv_details(self, credentials, db, ed, rec, us_state, exemption: str=None, refresh: bool=False)->(bool, str, DmvDetails):
        exemption = exemption or {
            'co': "tacDMV=DPPA-01",
            'fl': "tacDMV=DPPAFL-03",
            'ms': "tacDMV=DPPA-01",
            'tx': "tacDMV=DPPATX-01",
            'wv': "tacDMV=DPPA-01",
            'wi': "tacDMV=DPPA-01"
            }[us_state.lower()]
        (success, message, tree) = self.details(credentials, db, rec, ed, exemption, refresh)
        details = None
        if success:
            root = tree.getroot()
            fields = root.findall("./dataset/dataitem/textdata")
            details = DmvDetails()
            details.from_xml(fields[0], SOURCE, us_state)
            lien_holders = root.findall("./dataset/dataitem/dataset[@label='Lien Holders']")
            for lien in lien_holders:
                lien_holder = DmvLienHolder()
                lien_holder.from_xml(lien, SOURCE, us_state)
                details.lien_holders.append(lien_holder)

        return (success, message, details)

    def real_property(
        self,
        credentials: dict,
        search_terms: str,
        match_type: str="all",
        match_scope: str="name",
        us_state: str="tx",
        refresh: bool=False
    )->(bool, str, list):
        """
        Search Real Property records.

        Args:
            credentials (dict): username and password for Public Data service.
            search_terms (str): The text being searched
            match_type (str): "all" or "any" depending on how to want to search for each word in search_terms
            match_scope (str): Type of search: "main", "name"
            us_state (str): U.S. state to search, "*" = search all states
            refresh (bool): True to force a load from the remote URL; False to use recently cached result

        Returns:
            (
                (bool): Success?
                (str): Message explaining any error that's reported.
                (list): List of RealPropertySummary instances
            )
        """
        valid_states = StateAbbreviations
        if us_state.lower() not in valid_states and us_state != "*":
            message = "Cannot search for real property in {}. Can only search {}.".format(us_state, ", ".join(valid_states))
            return (False, message, [])

        if match_type.lower() not in ['all', 'any']:
            return (False, "Invalid match type: {}. Must be either 'any' or 'all'.".format(match_type), [])

        valid_scopes = ['main', 'name']
        if match_scope.lower() not in valid_scopes:
            message = "Invalid match scope: {}. Must be one of: {}".format(match_scope, ", ".join(valid_scopes))
            return (False, message, [])

        # Slight variation in database name, depending on which state
        if us_state == "*":
            db_name = f"grp_cad_advanced_{match_scope.lower()}"
        else:
            db_name = f"grp_cad_{us_state.lower()}_advanced_{match_scope.lower()}"
        summaries = []

        # Loop through paged results.
        more_pages = True
        searchmoreid = None
        max_pages = MAX_PAGES  # Not going to pull more than this many pages, no matter how many there are.
        while more_pages and max_pages > 0:
            (success, message, tree) = self.search(credentials,
                                                   db_name=db_name,
                                                   search_terms=search_terms,
                                                   match_scope=match_scope,
                                                   searchmoreid=searchmoreid)

            # If we encoutered a problem, return whatever we already accumluated, if anything
            if not success:
                return (False, message, summaries)

            # Successful search (meaning no errors)
            # Append results to our list of summaries are accumulating
            max_pages -= 1
            root = tree.getroot()
            properties = root.findall("./results/record")
            for item in properties:
                rp_summary = RealPropertySummary()
                rp_summary.from_xml(item, SOURCE, us_state.upper())
                summaries.append(rp_summary)

            # See if there are other pages of results to process.
            # print("IS MORE?",(root.findall("./results")[0].get("ismore")).lower())
            try:
                more_pages = (root.findall("./results")[0].get("ismore")).lower() == "true"
            except IndexError:
                more_pages = False

            # If there are more, get reference to the next page id.
            if more_pages:
                searchmoreid = root.findall("./results")[0].get("searchmoreid")

        return (success, message, summaries)

    def property_details(self, credentials: dict, db: str, ed: str, rec: str, us_state: str):
        (success, message, tree) = self.details(credentials, db, rec, ed, None, False)
        details = None
        if success:
            root = tree.getroot()

            # Extract county name from source attribution.
            # Example: <dataset label="Collin County (Texas) - Central Appraisal District" rec="52513587">
            attribution = root.findall("./dataset")[0].get("label")
            county_regex = r"^([A-Za-z\s]*)"
            matches = re.findall(county_regex, attribution)
            county = matches[0].replace(" County", "").strip()

            fields = root.findall("./dataset/dataitem/textdata")
            details = RealPropertyDetails(county=county)
            details.from_xml(fields[0], SOURCE, us_state)

        return (success, message, details)

    def details(self, credentials, db_name: str, record_id: str, edition: str, exemption: str=None, refresh: bool=False)->(bool, str, object):
        (success, msg, keys) = self.login(username=credentials["username"], password=credentials["password"])
        url = "https://{}/pddetails.php?db={}&rec={}&ed={}&dlnumber={}&id={}&disp=XML" \
              .format(keys["search_server"], db_name, record_id, edition, keys["login_id"], keys["id"])
        if exemption:
            url += "&{}".format(exemption)
        return self.load_xml(url, refresh=refresh)

    def search(
        self,
        credentials: dict,
        db_name: str,
        search_terms: str,
        match_type: str="all",
        match_scope: str="name",
        us_state: str="tx",
        refresh: bool=False,
        search_type: str="advanced",
        exemption: str=None,
        searchmoreid: str=None
    )->(bool, str, object):
        """
        Search for records. Results are cached for one day (until midnight, not necessarily 24 hours).

        Args:
            credentials (dict): username and password
            db_name (str): Name of database to search
            search_terms (str): Terms to search for in the records
            match_type (str): "all" to match all *search_terms* or "any" to match any *search_terms*.
            match_scope (str): "name" to search by the *name* field or "main" to search in all fields.
            us_state (str): Two-letter state abbreviation to search within.
            refresh (bool): If True, skips the cache and forces a refresh from PublicData. Otherwise returns
                            cached values from that same calendar date, if any.
            search_type (str): "advanced" - Any words or name fields
                               "dob" - Date of Birth search
                               "vin" - VIN
                               etc. Documented at http://www.publicdata.com/pdapidocs/pdsearchtypesdocs.php
            exemption (str): Exemption code when searching otherwise protected information.
            searchmoreid (str): Used in paging through results that have more than one page.

        Returns:
            (bool, str, object): The *bool* indicates success or failure.
                                 The *str* provides a diagnostic message.
                                 The *object* is an ET tree, if successful otherwise NoneType.
        """
        try:
            normalized_terms = normalize_search_terms(search_terms)
            (success, msg, keys) = self.login(username=credentials["username"], password=credentials["password"])
            url = "https://{}/pdsearch.php?p1={}&matchany={}&input={}&dlnumber={}&id={}&type={}&asinname={}&disp=XML" \
                  .format(keys["search_server"], normalized_terms, match_type, db_name, keys["login_id"], keys["id"], search_type, match_scope)
            if exemption:
                url = url + "&" + exemption
            if searchmoreid:
                url = url + "&searchmoreid=" + searchmoreid

            print(url)
            self.logger.error("URL: %s", url)

            # Load XML tree from file or URL
            return self.load_xml(url, refresh=refresh)
        except Exception as e:
            self.logger.error("Error retrieving from %s: %s", url, str(e))
            self.logger.exception(e)
            message = str(e)

        return (False, message, None)


def error_message(root)->str:
    """
    Find an error message in XML that has indicated an error.
    Unfortunately, the error message is not in the same place, depending on
    the error. Here we have a list of paths to search for and we go through
    them until we find a message or run out of places to look.

    Args:
        root (xml.etree.ElementTree): Root node of an element tree

    Returns:
        (str): Error message
        (NoneType): Indicates we didn't find a message.
    """

    # Paths we will search. We search in the order in which the path
    # appears in the *paths* list, so insert them in the order you want
    # them searched.
    #
    # I do not understand why find() fails and findall() works.
    # tjd 07/16/2019
    paths = ["message", "./pdheaders/pdheader1"]
    message = None
    for path in paths:
        message_node = root.findall(path)
        if message_node:
            message = message_node[0].text
            break

    return message


def today_yyyymmdd()->str:
    """
    Get the current date in YYYYMMDD format.

    Args:
        None.

    Returns:
        (str): Today's date in YYYYMMDD format.
    """
    return datetime.now().strftime("%Y%m%d")


def normalize_search_terms(search_terms: str)->str:
    """
    Normalize the search terms so that searching for "A b c" is the same as searching for
    "a b C", "B C A", etc.

    Args:
        search_terms (str): Space-delimited list of search terms.

    Returns:
        (str): Space-delimited search terms, lowercased and sorted.
    """
    if not search_terms:
        return search_terms

    terms = search_terms.lower().split(" ")
    terms.sort()
    return " ".join(terms)
