"""
baserecord.py - Class that other data classes extend.

Copyright (c) 2019 by Thomas J. Daley, J.D.
"""
import json

class BaseRecord(object):
    
    def to_dict(self)->dict:
        """
        Get dict representation of this instance.
        """
        result = {}
        for attr in [x for x in dir(self) if x[:2] != "__"]:
            value = getattr(self, attr)
            if not callable(value):
                result[attr] = value

        return result

    def to_json(self, indent:int=0)->str:
        """
        Get JSON-string representation of this instance
        """
        my_dict = self.to_dict()
        return json.dumps(my_dict)
