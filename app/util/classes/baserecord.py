"""
baserecord.py - Class that other data classes extend.

Copyright (c) 2019 by Thomas J. Daley, J.D.
"""
import json


class BaseRecord(object):
    
    MAPPINGS = []

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

    def from_xml(self, root, source:str, state:str):
        """
        Parses given XML tree into our standard format.

        Args:
            root (ET): XML element to Process
            source (str): Source database, e.g. "PUBLICDATA"
            state (str): U.S. State, e.g. "TX"
        """
        if source.upper() not in self.MAPPINGS:
            raise ValueError("No mappings for this source: {}".format(source))

        if state.upper() not in self.MAPPINGS[source]:
            raise ValueError("No {} mappings for this state: {}".format(source, state))

        mappings = self.MAPPINGS[source.upper()][state.upper()]

        # ET.dump(root)

        for mapping in mappings:
            path = ".//field[@label='{}']".format(mapping["label"])
            #print("looking for", path)
            elem = root.findall(path)
            if elem:
                if "prop" in mapping:
                    value = elem[0].get(mapping["prop"])
                else:
                    value = elem[0].text

                #print("\tfound:", value)
                if value:
                    # See if we need to transform the data in any way.
                    if "transform" in mapping and mapping["transform"]:
                        value  = mapping["transform"](value)

                    # If the target attribute already has a value, append this value
                    # to the existing value.
                    if getattr(self, mapping["attr"]):
                        existing_value = getattr(self, mapping["attr"])
                        value = existing_value + " / " + value
                    setattr(self, mapping["attr"], value)
            else:
                #print("\tnot found")
                pass
 
