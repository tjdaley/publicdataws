"""
zillow.py - Python API for Zillow searches.

Based on documentation available at: https://www.zillow.com/howto/api/GetSearchResults.htm

Copyright (c) 2019 by Thomas J. Daley, J.D. All Rights Reserved.
"""
__author__ = "Thomas J. Daley, J.D."
__version__ = "0.0.1"

from datetime import datetime
import os
import requests
import xml.etree.ElementTree as ET
import xml

from .database import Database
from .logger import Logger

SEARCH_URL = "https://www.zillow.com/webservice/GetSearchResults.htm?zws-id={}&address={}&citystatezip={}"
SOURCE = "ZILLOW"

class Zillow(object):
    """
    Encapsulates an interface into PublicData's web site via Python.
    """
    def __init__(self, zws_id:str):
        """
        Class Initializer.
        """
        self.logger = Logger.get_logger(log_name="pdws.api")
        self.zws_id = zws_id

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

            # Deserialize response to XML element tree
            tree = ET.ElementTree(ET.fromstring(content))

            # See if we got an error response.
            root = tree.getroot()
            return_code = root.find("./message/code").text
            if return_code != "0":
                message = root.find("./message/text").text
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

    def search(self, street_address:str, city_state_zip:str, refresh:bool=False)->(bool, str, object):
        """
        Search for Tax Records by state. Results are cached for one day (until midnight, not necessarily 24 hours).

        Args:
            street_address (str): Street address of subject property
            city_state_zip (str): City, state, and ZIP of subject property
            refresh (bool): If True, skips the cache and forces a refresh from PublicData. Otherwise returns
                            cached values from that same calendar date, if any.

        Returns:
            (bool, str, object): The *bool* indicates success or failure.
                                 The *str* provides a diagnostic message.
                                 The *object* is an ET tree, if successful otherwise NoneType.
        """
        try:
            url = SEARCH_URL \
                  .format(self.zws_id, street_address, city_state_zip)

            # Load XML tree from file or URL
            return self.load_xml(url, refresh=refresh)
        except Exception as e:
            self.logger.error("Error retrieving from %s: %s")
            self.logger.exception(e)
            message = str(e)

        return (False, message, None)
