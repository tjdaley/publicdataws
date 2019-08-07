"""
database.py - Class for access our persistent data store for publicdataws.

Copyright (c) 2019 by Thomas J. Daley, J.D. All Rights Reserved.
"""
__author__ = "Thomas J. Daley, J.D."
__version__ = "0.0.1"

from datetime import datetime, timedelta
import json
import pickle
import xml.etree.ElementTree as ET
import time

from pymongo import MongoClient
from bson.objectid import ObjectId

from .logger import Logger

DB_URL = "mongodb://ec2-54-235-51-13.compute-1.amazonaws.com:27017/"
DB_NAME = "discoverybot"
CACHE_TABLE_NAME = "search_cache"
USER_TABLE = "discoverybot_users"
CASE_TABLE = "cases"

class MissingFieldException(Exception):
    def __init__self(self, message:str):
        return super(message)

class Database(object):
    """
    Encapsulates a database accessor that is agnostic as to the underlying
    database product or implementation, e.g. mongo, mysql, dynamodb, flat files, etc.
    """
    def __init__(self):
        """
        Instance initializer.
        """
        self.client = None
        self.dbconn = None
        self.logger = Logger.get_logger(log_name="pdws.database")
        self.last_inserted_id = None

    def connect(self)->bool:
        """
        Connect to the underlying datastore.

        Returns:
            (bool): True if successful, otherwise False.
        """
        success = False

        try:
            self.logger.debug("Connecting to database %s at %s", DB_NAME, DB_URL)
            client = MongoClient(DB_URL)
            dbconn = client[DB_NAME]
            self.client = client
            self.dbconn = dbconn
            self.logger.info("Connected to database.")
            success = True
        except Exception as e:
            self.logger.error("Error connecting to database: %s", e)

        return success

    def test_connection(self)->bool:
        """
        Test the underlying connection.

        Returns:
            (bool): True if connection is OK.
        """
        try:
            self.client.admin.command('ismaster')
            status = True
        except Exception as e:
            self.logger.error("Error testing DB conenction: %s", e)
            status = False

        return status

    def insert_cache(self, source:str, query:str, result:object)->bool:
        """
        Record the fact that we have received a file. This method will throw an exception if it
        encounters one while serialzing the *result*.

        Args:
            source (str): Source that was queried, e.g. "PUBLICDATA"
            query (str): The query that was submitted, e.g. the URL
            result (object): The result was received. Will be searialzed to a string.

        Returns:
            (bool): True if successful, otherwise False
        """
        # Record is to be deleted from cache (or at least ignored) after the time-to-live time has passed.
        ttl = datetime.utcnow() + timedelta(days=3)
        #now = datetime.utcnow()
        # self.logger.debug("**** NOW={} TTL={}  DIFF={}".format(now, ttl, ttl-now))

        # Serialize the result
        (result_type, serialized_result) = self.serialize_cache_entry(result)

        # Record to insert
        record = record_from_dict({"source":source, "query":query, "result":serialized_result, "result_type":result_type, "ttl":ttl})
        filter = {"source":source, "query": query}

        mongo_result = self.dbconn[CACHE_TABLE_NAME].replace_one(filter, record, upsert=True)
        return True

    def check_cache(self, source:str, query:str)->object:
        """
        Look into the cache to see if we have a recent answer to this query. If so, reconstitute it and return it. Otherwise,
        return None. *Recent answer* means a response to this exact *query* upon this same *source* for which the *ttl* is not
        in the past.

        Args:
            source (str): Source to be queried
            query (str): The query to be submitted.

        Returns:
            (NoneType): If no recent cache entry was found.
            (dict): If recent entry was found and should be reconstituted as JSON.
            (xml.etree.ElementTree): If recent entry was found and sould be reconstituted as XML.
            (str): If recent entry was found and should be reconstituted as STR.
        """
        utc_now = datetime.utcnow()
        filter = {"source": source, "query": query, "ttl": {"$gt": utc_now}}
        document = self.dbconn[CACHE_TABLE_NAME].find_one(filter)

        if not document:
            return None

        return self.reconstitute_cached_response(document)

    def serialize_cache_entry(self, search_result:object)->(str, str):
        """
        Serialize a search response for saving to our cache.

        Will throw any exceptions encountered.

        Args:
            search_result (object): The result to be cached.

        Returns:
            (str, str): A reconstitution hint and a serialized result.
        """

        try:
            if isinstance(search_result, ET.ElementTree):
                result_type="XML"
                #root = search_result.getroot()
                #serialized_result = ET.tostring(root)
                serialized_result = pickle.dumps(search_result)
            elif isinstance(search_result, dict):
                result_type = "JSON"
                serialized_result = json.dumps(search_result)
            elif isinstance(search_result, str):
                result_type = "STR"
                serialized_result = search_result
            else:
                result_type = "PICKLE"
                serialized_result = pickle.dumps(search_result)

            return (result_type, serialized_result)
        except Exception as e:
            self.logger.error("Error serializing %s: %s", result_type, e)

        return (None, None)

    def reconstitute_cached_response(self, document)->object:
        """
        Reconstitute a serialzed search result.

        Args:
            document (): MongoDB document containing search result.

        Returns:
            (object): Search result reconstituted to its original form.
        """

        result_type = "[result_type not in document]"

        try:
            result_type = document["result_type"]
            serialized_result = document["result"]

            if result_type == "XML":
                # result = ET.fromstring(serialized_result)
                result = pickle.loads(serialized_result)
            elif result_type == "JSON":
                result = json.loads(serialized_result)
            elif result_type == "STR":
                result = serialized_result.copy()
            elif result_type == "PICKLE":
                result = pickle.loads(serialized_result)
            else:
                result = serialized_result.copy()

            return result
        except pickle.UnpicklingError as e:
            self.logger.error("Error deserializing from %s: %s", result_type, e)

        return None

    def get_query_cache(self, limit:int=50):
        """
        Retrieve the last _limit_ entries from the query cache.

        Args:
            limit (int): Maximum number of query cache entries to return.

        Returns:
            (list): List of matching documents
        """
        documents = self.dbconn[CACHE_TABLE_NAME].find().sort("_id", -1).limit(limit)
        return documents

    def get_query_cache_item_result(self, id:str):
        """
        Get a single query cache item from the database.

        Args:
            id (str): The _id of the query to be retrieved.

        Returns:
            Deserialized result.
        """
        filter = {"_id": ObjectId(id)}
        document = self.dbconn[CACHE_TABLE_NAME].find_one(filter)
        if not document:
            return None
        
        result = self.reconstitute_cached_response(document)
        return str(ET.tostring(result.getroot()))

    def add_case(self, fields:dict)->bool:
        """
        Add a case to the database.
        """
        # Convert from user's dict to our format
        record = record_from_dict(fields)

        # Check for missing fields
        missing = [field for field in ['email', 'cause_number', 'description'] \
                         if field not in record.keys()]
        if missing:
            raise MissingFieldException('Missing required field(s): {}'.format(", ".join(missing)))

        # Lookup the user to get the user's ID
        my_email = fields["email"].lower()
        user_doc = self.get_user({"email": my_email})

        if not user_doc:
            self.logger.error("Add Case: User not found for email '%s'.", my_email)
            return False

        # Normalize any fields before saving.
        record['user_id'] = user_doc["_id"]
        record['cause_number'] = record['cause_number'].upper()

        # Create filter of unique field value combinations
        filter = {"user_id": record["user_id"], "cause_number": record["cause_number"] }

        # Add (upsert) the record
        mongo_result = self.dbconn[CASE_TABLE].replace_one(filter, record, upsert=True)
        return True

    def get_case(self, fields:dict)->dict:
        """
        Retrieve a case for this user.
        """
        # Check for missing fields
        if "email" not in fields:
            raise MissingFieldException("'email' must be provided in fields list.")

        if "_id" not in fields:
            raise MissingFieldException("'_id' must be provided in fields list.")

        # Lookup the user to get the user's ID
        my_email = fields["email"].lower()
        user_doc = self.get_user({"email": my_email})
        if not user_doc:
            return {}

        # Create lookup filter
        filter = {}
        filter['_id'] = ObjectId(fields['_id'])
        filter['user_id'] = user_doc["_id"]

        # Locate matching record
        document = self.dbconn[CASE_TABLE].find_one(filter)
        return document

    def get_cases(self, fields:dict)->dict:
        """
        Retrieve all matching cases for this user.

        For now, we search by the user's email rather than a session id.
        """
        # Check for missing fields
        if "email" not in fields:
            raise MissingFieldException("'email' must be provided in fields list.")

        # Lookup the user to get the user's ID
        my_email = fields["email"].lower()
        user_doc = self.get_user({"email": my_email})
        if not user_doc:
            return {}

        filter = {'user_id': user_doc["_id"]}

        # Locate matching records
        documents = self.dbconn[CASE_TABLE].find(filter)
        return documents

    def update_case(self, fields:dict)->bool:
        """
        """
        # Check for missing fields
        missing = [field for field in ['email', 'cause_number'] \
                         if field not in fields.keys()]
        if missing:
            raise MissingFieldException('Missing required field(s): {}'.format(", ".join(missing)))

        # Lookup the user to get the user's ID
        my_email = fields["email"].lower()
        user_doc = self.get_user({"email": my_email})
        if not user_doc:
            return {}

        # Create lookup filter
        filter = {
            "user_id": user_doc["_id"],
            "_id": ObjectId(fields["_id"])
            }

        # Create local copy of fields
        new_vals = fields.copy()

        # Remove columns that can't be updated
        for key in ['_id', 'user_id']:
            if key in new_vals:
                del(new_vals[key])

        # Add update times
        new_vals.update(base_record())

        # Locate and update the matching record
        mongo_result = self.dbconn[CASE_TABLE].update_one(filter, {"$set":new_vals}, upsert=False)
        return mongo_result.modified_count == 1

    def del_case(self, fields:dict)->bool:
        """
        """
        missing = [key for key in ['email', 'cause_number'] if key not in fields]
        if missing:
            raise MissingFieldException("Missing required field(s): {}".format(", ".join(missing)))

        # Lookup the user to get the user's ID
        my_email = fields["email"].lower()
        user_doc = self.get_user({"email": my_email})
        if not user_doc:
            return {}

        # Create lookup filter
        filter = {
            "user_id": user_doc["_id"],
            "cause_number": fields["cause_number"].upper()
            }

        # Delete the case, if we can find it.
        mongo_result = self.dbconn[CASE_TABLE].remove(filter, {"justOne": True})
        return mongo_result["nRemoved"] == 1

    def add_user(self, fields:dict)->bool:
        """
        """
        if "email" in fields:
            fields["email"] = fields["email"].lower()

        record = record_from_dict(fields)
        filter = {"email": fields["email"]}
        document = self.dbconn[USER_TABLE].find_one(filter)

        if document:
            return False

        mongo_result = self.dbconn[USER_TABLE].replace_one(filter, record, upsert=True)
        return True

    def get_user(self, fields:dict)->dict:
        """
        """
        filter = fields.copy()
        if "email" in filter:
            filter["email"] = filter["email"].lower()

        document = self.dbconn[USER_TABLE].find_one(filter)
        return document

    def update_user(self, fields:dict)->dict:
        """
        """
        filter = {"email": fields['email']}
        mongo_result = self.dbconn[USER_TABLE].update_one(filter, {"$set":fields}, upsert=False)
        return mongo_result.modified_count == 1

def base_record()->dict:
    """
    Return a basic record with the audit flags we use in all records.

    Args:
        None

    Returns:
        (dict): dict with audit fields populated.
    """
    return {"time": time.time(), "time_str": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}

def record_from_dict(fields:dict, id_fields:list=[])->dict:
    """
    Create a record from a dict.

    Args:
        fields (dict): Dict of fields to add to the record.
        id_fields (list): List of fields that need to be converted to ObjectIds (optional)

    Returns:
        (dict): Standardized record.
    """
    record = base_record()
    for key, value in fields.items():
        if key in id_fields:
            record[key] = ObjectId(value)
        elif key not in record:
            record[key] = value

    return record
