"""
publicdata.py - Python API for Public Data searches.

Based on documentation available at: http://www.publicdata.com/pdapidocs/index.php

Copyright (c) 2019 by Thomas J. Daley, J.D. All Rights Reserved.
"""
__author__ = "Thomas J. Daley, J.D."
__version__ = "0.0.1"

from datetime import datetime
import os
import requests
import xml.etree.ElementTree as ET

from .logger import Logger


LOGIN_URL = "https://login.publicdata.com/pdmain.php/logon/checkAccess?disp=XML&login_id={}&password={}"

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

        # Should be same as username, but who knows if PD might manipulate it in the future.
        # Here we save the version they reported back in the login response so that we can include it
        # in queries and searches we make.
        self.login_id = None

        self.login_server = None
        self.search_server = None
        self.main_server = None

    def load_xml(self, filename:str, url:str)->(bool, str, object):
        """
        Load XML either from a cached file or a URL. If the cache file exists, we'll load from there.
        If the cache file does not exist, we'll load from the URL.

        Args:
            filename (str): Name of the cache file to try to load.
            url (str): URL to load from if cache file does not exist.

        Returns:
            (bool, str, object): The *bool* indicates success or failure.
                                 The *str* provides a diagnostic message.
                                 The *object* is an ET tree, if successful otherwise NoneType.
        """
        # See if the cache file exists. If so, it is not necessary
        # to query the URL - we will just parse the contents of the file.
        # TODO: Force load from URL if XML parse fails.
        try:
            if os.path.exists(filename):
                self.logger.debug("Parsing previous response from earlier today: %s.", filename)
                tree = ET.parse(filename)
            else:
                self.logger.debug("Load from URL.")

                # Retrieve response from server
                response = requests.get(url, allow_redirects=False)

                # Convert response from stream of bytes to string
                content = response.content.decode()

                # Save XML response
                open(filename, "w").write(content)
                tree = ET.fromstring(content)

            # See if we got an error response.
            root = tree.getroot()
            if root.get("type").lower() == "error":
                message = root.find("message").text
                return (False, message, tree)

            # All looks ok from a 30,000-foot level.
            return (True, "OK", tree)
        except Exception as e:
            self.logger.error("Error reading %s or loading from URL: %s", filename, e)
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
            (success, message, tree) = self.load_xml(xml_file_name, url)

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
            (success, message, tree) = self.load_xml(filename, url)

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

def today_yyyymmdd()->str:
    """
    Get the current date in YYYYMMDD format.

    Args:
        None.
    
    Returns:
        (str): Today's date in YYYYMMDD format.
    """
    return datetime.now().strftime("%Y%m%d")