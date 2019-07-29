"""
publicdata.py - Python API for Public Data searches.

Based on documentation available at: http://www.publicdata.com/pdapidocs/index.php

Copyright (c) 2019 by Thomas J. Daley, J.D. All Rights Reserved.
"""
__author__ = "Thomas J. Daley, J.D."
__version__ = "0.0.1"

import base64
from datetime import datetime
import os
import requests
import xml.etree.ElementTree as ET
import xml

from .database import Database
from .logger import Logger

from .classes.dmvdetails import DmvDetails
from .classes.dmvsummary import DmvSummary

LOGIN_URL = "https://login.publicdata.com/pdmain.php/logon/checkAccess?disp=XML&login_id={}&password={}"
SOURCE = "PUBLICDATA"

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

    def load_xml(self, url:str, refresh=False, filename:str=None)->(bool, str, object):
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

            self.logger.debug("Loading from URL.")

            # Retrieve response from server
            response = requests.get(url, allow_redirects=False)

            # Convert response from stream of bytes to string
            content = response.content.decode()
            #Sprint(content)

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

    def login(self, username:str, password:str)->(bool, str, dict):
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

    def tax_records(self, credentials:dict, search_terms:str, match_type:str="all", match_scope:str="name", us_state:str="tx", refresh:bool=False)->(bool, str, object):
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

    def dmv(self, credentials:dict, search_terms, match_type:str="all", match_scope:str="name", us_state:str="tx", refresh:bool=False, exemption:bool=None)->(bool, str, object):
        db_name = "{}dmv|{}".format(us_state, match_scope)
        summaries = []
        (success, message, tree) = self.search(credentials, db_name=db_name, search_terms=search_terms, match_scope="main", search_type="advanced", exemption="tacDMV=DPPATX-01")
        if success:
            root = tree.getroot()
            cars = root.findall("./results/record")
            for car in cars:
                dmv_summary = DmvSummary()
                dmv_summary.from_xml(car, SOURCE, us_state.upper())
                summaries.append(dmv_summary)
                
        return (success, message, summaries)

    def dmv_details(self, credentials, db, ed, rec, us_state, refresh:bool=False)->(bool, str, DmvDetails):
        (success, message, tree) = self.details(credentials, db, rec, ed, refresh)
        details = None
        if success:
            root = tree.getroot()
            fields = root.findall("./dataset/dataitem/textdata")
            details = DmvDetails()
            details.from_xml(fields[0], SOURCE, us_state)

        return (success, message, details)

    def details(self, credentials, db_name:str, record_id:str, edition:str, refresh:bool=False)->(bool, str, object):
        (success, msg, keys) = self.login(username=credentials["username"], password=credentials["password"])
        url = "http://{}/pddetails.php?db={}&rec={}&ed={}&dlnumber={}&id={}&disp=XML&tacDMV=DPPATX-01" \
               .format(keys["search_server"], db_name, record_id, edition, keys["login_id"], keys["id"])
        return self.load_xml(url, refresh=refresh)

    def search(self, credentials:dict, db_name:str, search_terms:str, match_type:str="all", match_scope:str="name", us_state:str="tx", refresh:bool=False, search_type:str="advanced", exemption:str=None)->(bool, str, object):
        """
        Search for Tax Records by state. Results are cached for one day (until midnight, not necessarily 24 hours).

        Args:
            credentials (dict): username and password
            db_name (str): Name of database to search
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
            normalized_terms = normalize_search_terms(search_terms)
            (success, msg, keys) = self.login(username=credentials["username"], password=credentials["password"])
            url = "http://{}/pdsearch.php?p1={}&matchany={}&input={}&dlnumber={}&id={}&type={}&asinname={}&disp=XML" \
                  .format(keys["search_server"], normalized_terms, match_type, db_name, keys["login_id"], keys["id"], search_type, match_scope)
            if exemption:
                url = url + "&" + exemption

            # Load XML tree from file or URL
            return self.load_xml(url, refresh=refresh)
        except Exception as e:
            self.logger.error("Error retrieving from %s: %s")
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

def normalize_search_terms(search_terms:str)->str:
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