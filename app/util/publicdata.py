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
        self.username = None
        self.password = None
        self.login_date = None
        self.hierarchy = []

        self.session_id = None
        self.id = None

        self.database = None
        self.connect_db()

        # Should be same as username, but who knows if PD might manipulate it in the future.
        # Here we save the version they reported back in the login response so that we can include it
        # in queries and searches we make.
        self.login_id = None

        self.login_server = None
        self.search_server = None
        self.main_server = None

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
            print(content)

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

    def login(self, username:str, password:str)->(bool, str):
        """
        Attempt to login to the PublicData servers.

        Args:
            username (str): The login_id to be used.
            password (str): The password to be used.

        Returns:
            (bool, str): Where the bool incates success ("True") or failure and the str is
                         a diagnostic message.
        """
        try:
            # Generate name of today's login response.
            xml_file_name = "{}-login.xml".format(today_yyyymmdd())
            # Format URL
            url = LOGIN_URL.format(username, password)
            # Load XML tree from file or URL
            (success, message, tree) = self.load_xml(url, filename=xml_file_name)

            if not success:
                return (success, message)

            # We have our XML tree, now process it.
            root = tree.getroot()
            self.login_date = today_yyyymmdd()

            child = root.find("user")
            self.id = child.find("id").text

            # If we get a NoneType *id*, the login failed.
            if not self.id:
                child = root.find("pdheaders")
                message = child.find("pdheader1").text
                return (False, message)

            # Successful login . . . keep going.
            self.session_id = child.find("sessionid").text
            self.login_id = child.find("dlnumber").text
            
            child = root.find("servers")
            self.search_server = child.find("searchserver").text
            self.login_server = child.find("loginserver").text
            self.main_server = child.find("mainserver").text
            # TODO: Check our remaining searches and post a warning if low and a panic message is depleted.

            return (True, "OK")
        except Exception as e:
            self.logger.error("Error connecting to %s: %s", LOGIN_URL, e)
            self.logger.exception(e)
            message = str(e)

        return (False, message)

    def tax_records(self, search_terms:str, match_type:str="all", match_scope:str="name", us_state:str="tx", refresh:bool=False)->(bool, str, object):
        """
        Search for Tax Records by state. Results are cached for one day (until midnight, not necessarily 24 hours).

        Args:
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
            return self.search(db_name, search_terms, match_type, match_scope, us_state, refresh)
        except Exception as e:
            self.logger.error("Error retrieving from %s: %s")
            self.logger.exception(e)
            message = str(e)

        return (False, message, None)

    def dmv(self, search_terms, match_type:str="all", match_scope:str="name", us_state:str="tx", refresh:bool=False, exemption:bool=None)->(bool, str, object):
        db_name = "{}dmv|{}".format(us_state, match_scope)
        summaries = []
        (success, message, tree) = self.search(db_name=db_name, search_terms=search_terms, match_scope="main", search_type="advanced", exemption="tacDMV=DPPATX-01")
        if success:
            root = tree.getroot()
            cars = root.findall("./results/record")
            for car in cars:
                dmv_summary = DmvSummary()
                dmv_summary.from_xml(car, SOURCE, us_state.upper())
                summaries.append(dmv_summary)
                
        return (success, message, summaries)

    def dmv_details(self, summary, refresh:bool=False)->(bool, str, DmvDetails):
        (success, message, tree) = self.details(summary.db, summary.rec, summary.ed, refresh)
        if success:
            root = tree.getroot()
            fields = root.findall("./dataset/dataitem/textdata")
            details = DmvDetails()
            details.from_xml(fields[0], SOURCE, summary.state)
            return (success, message, details)
        return (success, message, None)

    def details(self, db_name:str, record_id:str, edition:str, refresh:bool=False)->(bool, str, object):
        url = "http://{}/pddetails.php?db={}&rec={}&ed={}&dlnumber={}&id={}&disp=XML&tacDMV=DPPATX-01" \
               .format(self.search_server, db_name, record_id, edition, self.login_id, self.id)
        return self.load_xml(url, refresh=refresh)

    def search(self, db_name:str, search_terms:str, match_type:str="all", match_scope:str="name", us_state:str="tx", refresh:bool=False, search_type:str="advanced", exemption:str=None)->(bool, str, object):
        """
        Search for Tax Records by state. Results are cached for one day (until midnight, not necessarily 24 hours).

        Args:
            database (str): Name of database to search
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
            url = "http://{}/pdsearch.php?p1={}&matchany={}&input={}&dlnumber={}&id={}&type={}&asinname={}&disp=XML" \
                  .format(self.search_server, normalized_terms, match_type, db_name, self.login_id, self.id, search_type, match_scope)
            if exemption:
                url = url + "&" + exemption

            # Load XML tree from file or URL
            return self.load_xml(url, refresh=refresh)
        except Exception as e:
            self.logger.error("Error retrieving from %s: %s")
            self.logger.exception(e)
            message = str(e)

        return (False, message, None)

    def document(self, db_label:str = "grp_master")->(dict):
        """
        Generate documentation for the databases.

        Args:
            None.

        Returns:
            (dict): A dict describing the databases availble for querying.
        """
        (success, message, subdbs, group_flag) = self.query(db_label=db_label)
        self.hierarchy.append(subdbs)

        if group_flag == "selfrom":
            for key in subdbs.keys():
                self.document(key)

        #self.logger.debug("%s", self.hierarchy)

        return (True, "OK", self.hierarchy, "DONE")

    def query(self, db_label:str = "grp_master")->(bool, str, dict, str):
        """
        Performs a PDquery, which "is used to find a current database or group of databases to search."

        Returns:
            (bool, str, dict, str): Where the *bool* incates success ("True") or failure;
                                    the *str* is a diagnostic message;
                                    the *dict* is the results of the query; and
                                    the *str* is "selfrom", meaning there are further sub-databases, or not.
        """
        try:
            # Get and save response
            filename_pattern = "{}-query-{}.xml".format(today_yyyymmdd(), "{}")
            url_pattern = "http://{}/pdquery.php?o={}&dlnumber={}&id={}&disp=XML" \
                  .format(self.search_server, "{}", self.login_id, self.id)
            url = url_pattern.format(db_label)
            filename = filename_pattern.format(db_label)
            (success, message, tree) = self.load_xml(url, filename=filename)

            if not success:
                return (success, message, None, "err")

            # Process response
            root = tree.getroot()

            # Find out is this db is searable or a group with sub-databases
            query_type = root.find("querydata").get("type")

            child = root.find("groupentries")

            #self.logger.info("The following databases are available for search:")
            doc = {} # Documentation
            for item in child.findall("item"):
                desc = item.text
                db_name = item.get("label")
                db_type = item.get("type")
                db_prot = item.get("tactype") or "None"
                #self.logger.info("%-30s - %-12s (%-10s) - Protection: %s", desc, db_name, db_type, db_prot)
                doc[db_name] = {"desc":desc, "name":db_name, "type":db_type, "prot":db_prot}

            return (True, "OK", doc, query_type)
        except Exception as e:
            self.logger.error("Error querying %s: %s", url, e)
            self.logger.exception(e)
            return (False, str(e), None, "err")

        return (False, "Programmer error", None, "err")

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