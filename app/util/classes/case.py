"""
case.py - Represents a client's case.

Copyright (c) 2019 by Thomas J. Daley, J.D.
"""
__author__ =  "Thomas J. Daley, J.D."
__version__ = "0.0.1"

from .baserecord import BaseRecord

class Case(BaseRecord):
    required_properties = [
        'cause_number',
        'county',
        'us_state',
        'case_name',
        'created_by'
    ]

    """
    Encapsulates a client case.
    """
    def __init__(self, fields:dict):
        """
        Instance initializer.
        """
        self.cause_number = None
        self.county = None
        self.us_state = None
        self.name = None
        self.created_by = None

        # Caller can set whatever fields it thinks it wants
        for key, value in fields.items():
            setattr(self, key, value)

        # But it must have at least these named arguments
        missing = self.check_required_props()
        if missing:
            raise Exception("Required named argument missing: {}".format(", ".join(missing)))

    def check_required_props(self)->list:
        """
        Make sure we have all the required properties.

        Returns:
            list: List of missing property names.
        """
        missing = [prop for prop in self.required_properties if not getattr(self, prop)]
        return missing