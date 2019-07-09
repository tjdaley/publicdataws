"""
webservice.py - Webservice for PublicData

Copyright (c) 2019 by Thomas J. Daley, J.D. All Rights Reserved.
"""
__author__ = "Thomas J. Daley, J.D."
__version__ = "0.0.1"

import argparse
import json

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

    def query(self)->(bool, str):
        """
        Query the PublicData service.

        Args:
            None.
        Returns:
            (bool, str): Where *bool* indicates success or failure and *str* provides an explanatory message.
        """
        return self.api.document()


def main(args:{}):
    webservice = WebService(args.username, args.password)
    print(webservice.connect())
    success, message, doc, status = webservice.query()
    outstr = json.dumps(doc, indent=4)
    open("20190709-ALLDB.json", "w").write(outstr)
    print(outstr)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Webservice for PublicData")
    parser.add_argument("--username", "-u", required=True, help="Username for logging into the PublicData service.")
    parser.add_argument("--password", "-p", required=True, help="Password for logging into the PublicData service.")
    args = parser.parse_args()
    main(args)
