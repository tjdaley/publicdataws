"""
database.py - Class for access our persistent data store for publicdataws.

@author Thomas J. Daley, J.D.
@version 0.0.2
@Copyright (c) 2019 by Thomas J. Daley, J.D. All Rights Reserved.
TODO: With the 2 Sep 2019 code reorg/refactor, this needs to operate as a
      singleton.
      At this time, we have lots of individual database connections--one for
      each time this class is imported.

Copyright (c) 2019 by Thomas J. Daley, J.D. All Rights Reserved.
"""
from datetime import datetime, timedelta
import json
import os
from operator import itemgetter
import pickle
import xml.etree.ElementTree as ET
import xml.dom.minidom as MD
import time

from pymongo import MongoClient, ReturnDocument
from bson.objectid import ObjectId
from bson.errors import InvalidId

from .logger import Logger
from .texasbarsearch import TexasBarSearch

BARSEARCH = TexasBarSearch()

DB_URL = 'mongodb://ec2-54-235-51-13.compute-1.amazonaws.com:27017/'

try:
    DB_URL = os.environ["DB_URL"]
except KeyError as e:
    Logger.get_logger(log_name="pdws.database") \
        .fatal(
            "Database connection string environment variable is not set: %s",
            str(e))
    exit()

DB_NAME = 'discoverybot'
CACHE_TABLE_NAME = 'search_cache'
USER_TABLE = 'discoverybot_users'
CASE_TABLE = 'cases'
DISCOVERY_TABLE = 'discovery_requests'


class MissingFieldException(Exception):
    def __init__self(self, message: str):
        return super(message)


class Database(object):
    """
    Encapsulates a database accessor that is agnostic as to the underlying
    database product or implementation, e.g. mongo, mysql, dynamodb, flat
    files, etc.
    """
    def __init__(self):
        """
        Instance initializer.
        """
        self.client = None
        self.dbconn = None
        self.logger = Logger.get_logger(log_name="pdws.database")
        self.last_inserted_id = None

    def connect(self) -> bool:
        """
        Connect to the underlying datastore.

        Returns:
            (bool): True if successful, otherwise False.
        """
        success = False

        try:
            # pep8: disable E501
            self.logger.debug(
                "Connecting to database %s at %s",
                DB_NAME,
                DB_URL)
            client = MongoClient(DB_URL)
            dbconn = client[DB_NAME]
            self.client = client
            self.dbconn = dbconn
            self.logger.info("Connected to database.")
            success = True
        except Exception as e:
            self.logger.error("Error connecting to database: %s", e)

        return success

    def test_connection(self) -> bool:
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

    def insert_cache(self, source: str, query: str, result: object) -> bool:
        """
        Record the fact that we have received a file. This method will throw
        an exception if it encounters one while serialzing the *result*.

        Args:
            source (str): Source that was queried, e.g. "PUBLICDATA"
            query (str): The query that was submitted, e.g. the URL
            result (object): The result was received. Will be searialzed to a
            string.

        Returns:
            (bool): True if successful, otherwise False
        """
        # Record is to be deleted from cache (or at least ignored) after the
        # time-to-live time has passed.
        ttl = datetime.utcnow() + timedelta(days=3)

        # Serialize the result
        (result_type, serialized_result) = self.serialize_cache_entry(result)

        # Record to insert
        record = record_from_dict({
            "source": source,
            "query": query,
            "result": serialized_result,
            "result_type": result_type,
            "ttl": ttl})
        filter = {"source": source, "query": query}

        mongo_result = self.dbconn[CACHE_TABLE_NAME].replace_one(filter, record, upsert=True)
        self.logger.debug("mongo_result of replace_one: %s", mongo_result)
        return True

    def check_cache(self, source: str, query: str) -> object:
        """
        Look into the cache to see if we have a recent answer to this query.
        If so, reconstitute it and return it. Otherwise, return None.
        *Recent answer* means a response to this exact *query* upon this same
        *source* for which the *ttl* is not in the past.

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

    def serialize_cache_entry(self, search_result: object) -> (str, str):
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
                result_type = "XML"
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

    def reconstitute_cached_response(self, document) -> object:
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

    def get_query_cache(self, limit: int = 50):
        """
        Retrieve the last _limit_ entries from the query cache.

        Args:
            limit (int): Maximum number of query cache entries to return.

        Returns:
            (list): List of matching documents
        """
        documents = self.dbconn[CACHE_TABLE_NAME].find().sort("_id", -1).limit(limit)
        return documents

    def get_query_cache_item_result(self, id: str):
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
        rough_string = ET.tostring(result.getroot(), 'utf-8')
        reparsed = MD.parseString(rough_string)
        return reparsed.toprettyxml(indent="   ")

    def get_user_id_for_email(self, email: str) -> ObjectId:
        """
        Return the _id field for the user identified by the given email address.

        Args:
            email (str): Email address to search.

        Returns:
            (ObjectId): ID of the user we found or None if not found.
        """
        user_doc = self.get_user({"email": email})
        if user_doc:
            return user_doc["_id"]
        return None

    def attorney(self, bar_number: str) -> dict:
        """
        Search for an attorney by bar number.

        Args:
            bar_number (str): The attorney's Texas Bar number.
        Returns:
            (dict): Descriptive data about the attorney
        """
        return BARSEARCH.find(bar_number)

    def add_case(self, fields: dict) -> bool:
        """
        Add a case to the database.
        """
        # Convert from user's dict to our format
        record = record_from_dict(fields)

        # Check for missing fields
        missing = [field for field in ['email', 'cause_number', 'description']
                   if field not in record.keys()]
        if missing:
            raise MissingFieldException('Missing required field(s): {}'.format(", ".join(missing)))

        # Lookup the user to get the user's ID
        my_email = fields["email"].lower()
        user_id = self.get_user_id_for_email(my_email)
        if not user_id:
            self.logger.error("database.add_case(): Email not found: '%s'", my_email)
            return False

        # Normalize any fields before saving.
        record['user_id'] = user_id
        record['cause_number'] = record['cause_number'].upper()

        # Create filter of unique field value combinations
        filter = {"user_id": record["user_id"], "cause_number": record["cause_number"]}

        # Add (upsert) the record
        mongo_result = self.dbconn[CASE_TABLE].replace_one(filter, record, upsert=True)
        return True

    def get_case(self, fields: dict) -> dict:
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
        user_id = self.get_user_id_for_email(my_email)
        if not user_id:
            self.logger.error("database.get_case(): Email not found: '%s'", my_email)
            return {}

        # Create lookup filter
        filter = {}
        filter['_id'] = ObjectId(fields['_id'])
        filter['user_id'] = user_id

        # Locate matching record
        document = self.dbconn[CASE_TABLE].find_one(filter)
        return document

    def get_cases(self, fields: dict) -> dict:
        """
        Retrieve all matching cases for this user.

        For now, we search by the user's email rather than a session id.
        """
        # Check for missing fields
        if "email" not in fields:
            raise MissingFieldException("'email' must be provided in fields list.")

        # Lookup the user to get the user's ID
        my_email = fields["email"].lower()
        user_id = self.get_user_id_for_email(my_email)
        if not user_id:
            self.logger.error("database.get_cases(): Email not found: '%s'", my_email)
            return {}

        filter = {'user_id': user_id}

        # Locate matching records
        documents = self.dbconn[CASE_TABLE].find(filter)
        return documents

    def update_case(self, fields: dict) -> bool:
        """
        """
        # Check for missing fields
        missing = [field for field in ['email', 'cause_number']
                   if field not in fields.keys()]
        if missing:
            raise MissingFieldException('Missing required field(s): {}'.format(", ".join(missing)))

        # Lookup the user to get the user's ID
        my_email = fields["email"].lower()
        user_id = self.get_user_id_for_email(my_email)
        if not user_id:
            self.logger.error("database.update_case(): Email not found: '%s'", my_email)
            return False

        # Create lookup filter
        filter = {
            "user_id": user_id,
            "_id": ObjectId(fields["_id"])}

        # Create local copy of fields
        new_vals = fields.copy()

        # Remove columns that can't be updated
        for key in ['_id', 'user_id']:
            if key in new_vals:
                del(new_vals[key])

        # Add update times
        new_vals.update(base_record())

        # Locate and update the matching record
        mongo_result = self.dbconn[CASE_TABLE].update_one(filter, {"$set": new_vals}, upsert=False)
        return mongo_result.modified_count == 1

    def del_case(self, fields: dict) -> bool:
        """
        """
        missing = [key for key in ['email', 'cause_number'] if key not in fields]
        if missing:
            raise MissingFieldException("Missing required field(s): {}".format(", ".join(missing)))

        # Lookup the user to get the user's ID
        my_email = fields["email"].lower()
        user_id = self.get_user_id_for_email(my_email)
        if not user_id:
            self.logger.error("database.del_case(): Email not found: '%s'", my_email)
            return False

        # Create lookup filter
        filter = {
            "user_id": user_id,
            "cause_number": fields["cause_number"].upper()}

        # Delete the case, if we can find it.
        mongo_result = self.dbconn[CASE_TABLE].remove(filter, {"justOne": True})
        return mongo_result["nRemoved"] == 1

    def add_to_case(self, email: str, case_id: str, category: str, key: str, fields: dict) -> bool:
        """
        Add an item, such as property or a person, to a case record.

        Args:
            email (str): Email address of person trying to add
            case_id (str): String version of _id field of case to be added to.
            category (str): Category name. Can optionally contain a
                subcategory delimited by a colon (":").
                E.G. "PROPERTY:VEHICLE", "PROPERTY:REAL",
                "PROPERTY:BANK_ACCOUNT"
            key (str): Application-generated key for this item, e.g., for
                Public Data it could take the form PUBLICDATA:<db>:<ed>:<rec>
            fields (dict): Property values for this item.

        Returns:
            (bool): True if successful, otherwise False
        """

        # Get user_id for the given email
        user_id = self.get_user_id_for_email(email)
        if not user_id:
            self.logger.error("database.add_to_case(): Email not found: '%s'", email)
            return False

        # Get make sure this user owns the case.
        my_case_id = ObjectId(case_id)
        filter = {
            "_id": my_case_id,
            "user_id": user_id
        }
        case_doc = self.dbconn[CASE_TABLE].find_one(filter)
        if not case_doc:
            self.logger.error("database.add_to_case(): Case '%s' not found for '%s'", case_id, email)
            return False

        # Make sure case has discovery items dictionary.
        if "discovery" not in case_doc:
            case_doc["discovery"] = {}

        discovery = case_doc["discovery"]

        # Create item collection to add to, if not already there.
        (main_cat, sub_cat) = split_category(category)
        if main_cat not in discovery:
            discovery[main_cat] = {}

        if sub_cat and sub_cat not in discovery[main_cat]:
            discovery[main_cat][sub_cat] = {}

        # Now insert or update the corresponding key into the case document.
        subrecord = record_from_dict(fields)
        if not sub_cat:
            discovery[main_cat][key] = subrecord
        else:
            discovery[main_cat][sub_cat][key] = subrecord

        # Finally, save the updated case document.
        # Create local copy of fields
        new_vals = {key: value for key, value in case_doc.items() if key not in ['_id', 'user_id']}

        # Add update times
        new_vals.update(base_record())

        # Locate and update the matching record
        mongo_result = self.dbconn[CASE_TABLE].update_one(filter, {"$set": new_vals}, upsert=False)
        return mongo_result.modified_count == 1

    def del_from_case(self, email: str, case_id: str, category: str, key: str, fields: dict) -> bool:
        """
        Delete an item, such as property or a person, from a case record.

        Args:
            email (str): Email address of person trying to add
            case_id (str): String version of _id field of case to be added to.
            category (str): Category name. Can optionally contain a subcategory delimited by
                a colon (":"). E.G. "PROPERTY:VEHICLE", "PROPERTY:REAL", "PROPERTY:BANK_ACCOUNT"
            key (str): Application-generated key for this item, e.g., for Public Data it could
                take the form PUBLICDATA:<db>:<ed>:<rec>
            fields (dict): Property values for this item.

        Returns:
            (bool): True if successful, otherwise False
        """

        # Get user_id for the given email
        user_id = self.get_user_id_for_email(email)
        if not user_id:
            self.logger.error("database.del_from_case(): Email not found: '%s'", email)
            return False

        # Get make sure this user owns the case.
        my_case_id = ObjectId(case_id)
        filter = {
            "_id": my_case_id,
            "user_id": user_id
        }
        case_doc = self.dbconn[CASE_TABLE].find_one(filter)
        if not case_doc:
            self.logger.error("database.del_from_case(): Case '%s' not found for '%s'", case_id, email)
            return False

        # See if item collection exists. Return True if the collection does
        # not exist because there is nothing to delete.
        if "discovery" not in case_doc:
            return True

        discovery = case_doc["discovery"]

        (main_cat, sub_cat) = split_category(category)
        if main_cat not in discovery:
            return True

        if sub_cat and sub_cat not in discovery[main_cat]:
            return True

        # Now remove the corresponding key into the case document.
        try:
            if not sub_cat:
                del discovery[main_cat][key]
            else:
                del discovery[main_cat][sub_cat][key]
        except KeyError:
            return True  # It's already gone.

        # Finally, save the updated case document.
        # Create local copy of fields
        new_vals = {key: value for key, value in case_doc.items() if key not in ['_id', 'user_id']}

        # Add update times
        new_vals.update(base_record())

        # Locate and update the matching record
        mongo_result = self.dbconn[CASE_TABLE].update_one(filter, {"$set": new_vals}, upsert=False)
        return mongo_result.modified_count == 1

    def get_discovery_list(self, fields: dict) -> list:
        """
        Get a list of written discovery documents.
        """
        # Check for missing fields
        if 'email' not in fields:
            raise MissingFieldException("'email' must be provided in fields list.")
        if 'scope' not in fields:
            raise MissingFieldException("'scope' of 'all' or 'cause_number' must be provided in fields list")
        if fields['scope'] not in ['all', 'cause_number']:
            raise ValueError('scope must be "all" or "cause_number", not "{}"'.format(fields['scope']))
        if fields['scope'] == 'cause_number' and 'cause_number' not in fields:
            raise MissingFieldException("'cause_number' must be provided in fields list.")

        # Lookup the user to get the user's ID
        my_email = fields["email"].lower()
        user_id = self.get_user_id_for_email(my_email)
        if not user_id:
            self.logger.error("database.get_cases(): Email not found: '%s'", my_email)
            return {}

        # Create a filter based on our scope
        if fields['scope'] == 'all':
            match = {
                '$match': {
                    'owner': fields['email'].lower()
                }
            }
        else:
            match = {
                '$match': {
                    'owner': fields['email'].lower(),
                    'cause_number': fields['cause_number'],
                }
            }
        lookup = {'$lookup': {
            'from': CASE_TABLE,
            'localField': 'cause_number',
            'foreignField': 'cause_number',
            'as': 'case'
            }
        }
        documents = self.dbconn[DISCOVERY_TABLE].aggregate([match, lookup])
        return documents

    def get_discovery_requests(self, fields: dict) -> list:
        """
        Get a list of written discovery requests from one document
        """
        # Check for missing fields
        if 'email' not in fields:
            raise MissingFieldException("'email' must be provided in fields list.")
        if 'id' not in fields:
            raise MissingFieldException("'id' must be provided in fields list")

        # Lookup the user to get the user's ID
        my_email = fields["email"].lower()
        user_id = self.get_user_id_for_email(my_email)
        if not user_id:
            self.logger.error("database.get_cases(): Email not found: '%s'", my_email)
            return {}

        # Create a filter
        filter = {
            '_id': ObjectId(fields['id']),
            'owner': fields['email'].lower(),
        }

        # Locate matching records
        document = self.dbconn[DISCOVERY_TABLE].find(filter)
        if document.count() > 0:
            return document[0]
        return None

    def get_discovery_document(self, fields: dict) -> dict:
        """
        Get a discovery docuemnt by document _id.
        """
        if 'email' not in fields:
            raise MissingFieldException("'email' must be provided in fields list.")
        if 'id' not in fields:
            raise MissingFieldException("'id' must be provided in fields list")

        filter = {
            '_id': ObjectId(fields['id']),
            'owner': fields['email'],
        }

        doc = self.dbconn[DISCOVERY_TABLE].find_one(filter)
        return doc

    def save_discovery_document(self, fields: dict) -> bool:
        """
        Save a discovery document.
        """
        if 'email' not in fields:
            raise MissingFieldException("'email' must be provided in fields list.")

        attorney = self.attorney(fields['requesting_bar_num'])

        self.logger.debug(fields)
        self.logger.debug(attorney)

        if '_id' in fields:
            # Update
            filter = {
                '_id': ObjectId(fields['_id']),
                'owner': fields['email']
            }

            update = {
                '$set': {
                    'court_type': fields['court_type'],
                    'court_number': fields['court_number'],
                    'county': fields['county'],
                    'cause_number': fields['cause_number'],
                    'discovery_type': fields['discovery_type'],
                    'owner': fields['email'],
                    'requesting_attorney.bar_number': fields['requesting_bar_num'],
                    'requesting_attorney.email': fields['requesting_email'],
                    'requesting_attorney.details': attorney,
                }
            }

            mongo_result = self.dbconn[DISCOVERY_TABLE].update_one(
                filter,
                update,
                upsert=False
            )
            return mongo_result.modified_count == 1

        # Insert
        requesting_attorney = {
            'bar_number': fields['requesting_bar_num'],
            'email': fields['requesting_email'],
            'details': attorney,
        }
        doc = {
            "time": time.time(),
            "time_str": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            'court_type': fields['court_type'],
            'court_number': fields['court_number'],
            'county': fields['county'],
            'cause_number': fields['cause_number'],
            'discovery_type': fields['discovery_type'],
            'owner': fields['email'],
            'requesting_attorney': requesting_attorney,
            'cleaned_up': 0,
        }

        mongo_result = self.dbconn[DISCOVERY_TABLE].insert_one(doc)
        return mongo_result.inserted_id is not None

    def update_discovery_document_field(self, fields: dict) -> bool:
        """
        Update one field in a discovery document.
        """
        if 'email' not in fields:
            raise MissingFieldException("'email' must be provided in fields list.")
        if 'id' not in fields:
            raise MissingFieldException("'id' must be provided in fields list")
        if 'key' not in fields:
            raise MissingFieldException("'key' must be provided in fields list.")
        if 'value' not in fields:
            raise MissingFieldException("'value' must be provided in fields list")

        filter = {
            '_id': ObjectId(fields['id']),
            'owner': fields['email'],
        }

        update = {
            '$set': {fields['key']: fields['value']}
        }

        self.dbconn[DISCOVERY_TABLE].update(filter, update)
        return True

    def del_discovery_document(self, fields: dict) -> bool:
        """
        Delete a single discovery document.
        """
        if 'email' not in fields:
            raise MissingFieldException("'email' must be provided in fields list.")
        if 'id' not in fields:
            raise MissingFieldException("'id' must be provided in fields list")

        filter = {
            '_id': ObjectId(fields['id']),
            'owner': fields['email'],
        }

        mongo_result = self.dbconn[DISCOVERY_TABLE].delete_one(filter)
        return mongo_result.deleted_count == 1

    def save_discovery_request(self, fields: dict) -> bool:
        """
        Save an individual discovery request's text.
        """
        if 'email' not in fields:
            raise MissingFieldException("'email' must be provided in fields list.")
        if 'id' not in fields:
            raise MissingFieldException("'id' must be provided in fields list")
        if 'request_text' not in fields:
            raise MissingFieldException("'request_text' must be provided in fields list")

        filter = {
            '_id': ObjectId(fields['id']),
            'owner': fields['email'],
        }
        # Here to update an existing request
        if 'request_number' in fields:
            # _id = Unique ID of the discovery document that contains the request.
            # owner = Email address of user who owns the discovery document.
            # requests.number = Index into requests[] contained in discovery document
            filter['requests.number'] = int(fields['request_number'])

            update = {
                '$set': {'requests.$.request': fields['request_text']}
            }
            # Here to add a new discovery request this document.
        else:
            doc = self.get_discovery_document(fields)
            request_number = next_available_request_number(doc['requests'])
            request = {
                'number': request_number,
                'request': fields['request_text']
            }
            update = {
                '$push': {'requests': request}
            }

        self.dbconn[DISCOVERY_TABLE].update(filter, update)
        return True

    def del_discovery_request(self, fields: dict) -> bool:
        """
        Delete an individual dicovery request from a document.
        """
        if 'email' not in fields:
            raise MissingFieldException("'email' must be provided in fields list.")
        if 'id' not in fields:
            raise MissingFieldException("'id' must be provided in fields list")
        if 'request_number' not in fields:
            raise MissingFieldException("'email' must be provided in fields list.")

        filter = {
            '_id': ObjectId(fields['id']),
            'owner': fields['email']
        }

        update = {
            '$pull': {
                "requests": {
                    "number": int(fields["request_number"])
                }
            }
        }

        doc = self.dbconn[DISCOVERY_TABLE].find_one_and_update(
            filter=filter,
            update=update,
            return_document=ReturnDocument.AFTER,
        )
        return True

    def get_case_items(self, email: str, case_id: str, category: str = None) -> list:
        """
        Get a list of case items by category, e.g. "PROPERTY" or "PROPERTY:VEHICLE"

        Args:
            email (str): Email of person requesting access.
            case_id (str): _id of record in cases collection.
            category (str): Category name. Can optionally contain a subcategory delimited by
                a colon (":"). E.G. "PROPERTY:VEHICLE", "PROPERTY:REAL", "PROPERTY:BANK_ACCOUNT"

        Returns:
            (list): List of items found, or empty list if nothing found.
        """
        # Verify that case_id is a valid ObjectId.
        # An invalid ID probably means that the case_id is not set on the client-side, which is
        # not really an error, but a normal state. We catch that state here so that we can focus
        # the error handling where it is most easily caught.
        try:
            my_case_id = ObjectId(case_id)
        except InvalidId as e:
            self.logger.debug("database.get_case_items(): Invalid case_id: '%s'", case_id)
            return []

        # Get user_id for the given email
        user_id = self.get_user_id_for_email(email)
        if not user_id:
            self.logger.error("database.get_case_items(): Email not found: '%s'", email)
            return False

        # Get make sure this user owns the case.
        filter = {
            "_id": my_case_id,
            "user_id": user_id
        }
        case_doc = self.dbconn[CASE_TABLE].find_one(filter)
        if not case_doc:
            self.logger.error("database.get_case_items(): Case '%s' not found for '%s'", case_id, email)
            return False

        # See if we have any discovery added to this case.
        if "discovery" not in case_doc:
            self.logger.info("database.get_case_items(): Case '%s' does not have any discovery.", case_id)
            return []

        discovery = case_doc["discovery"]

        # If the caller did not specify a category, send all discovery back.
        if not category:
            return discovery

        # Split the category
        (main_cat, sub_cat) = split_category(category)

        if main_cat not in discovery:
            self.logger.info("database.get_case_items(): Case '%s' does not have category '%s'", case_id, main_cat)
            return []

        if sub_cat and sub_cat not in discovery[main_cat]:
            self.logger.info("database.get_case_items(): Case '%s' does not have sub-category '%s->%s'", case_id, main_cat, sub_cat)
            return []

        # Return the requested items
        if sub_cat:
            return discovery[main_cat][sub_cat]

        return discovery[main_cat]

    def add_user(self, fields: dict) -> bool:
        """
        """
        if "email" in fields:
            fields["email"] = fields["email"].lower()

        record = record_from_dict(fields)
        filter = {"email": fields["email"]}
        document = self.dbconn[USER_TABLE].find_one(filter)

        if document:
            self.logger.error("database.add_user(): email '%s' already exists.", fields['email'])
            return False

        mongo_result = self.dbconn[USER_TABLE].replace_one(filter, record, upsert=True)
        return True

    def get_user(self, fields: dict) -> dict:
        """
        """
        filter = fields.copy()
        if "email" in filter:
            filter["email"] = filter["email"].lower()

        document = self.dbconn[USER_TABLE].find_one(filter)
        return document

    def update_user(self, fields: dict) -> dict:
        """
        """
        filter = {"email": fields['email']}
        mongo_result = self.dbconn[USER_TABLE].update_one(filter, {"$set": fields}, upsert=False)
        return mongo_result.modified_count == 1

    # Helper to stringify ObjectId variables so they can be saved in a session.
    def safe_dict(self, d: dict) -> dict:
        """
        Stringify ObjectIds. Some operations try to serialize a dictionary and
        serialization fails (for some reason) if the dict contains an ObjectId.
        This helper converts ObjectIds to strings. The input dictionary is not affected.

        Args:
            d (dict): The dictionary to process.

        Returns:
            (dict): Dictionary with ObjectIds converted to strings
        """
        result = {}
        for key, value in d.items():
            if isinstance(value, ObjectId):
                result[key] = str(value)
            else:
                result[key] = value
        return result


def base_record() -> dict:
    """
    Return a basic record with the audit flags we use in all records.

    Args:
        None

    Returns:
        (dict): dict with audit fields populated.
    """
    return {"time": time.time(), "time_str": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}


def record_from_dict(fields: dict, id_fields: list = []) -> dict:
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


def split_category(category: str):
    """
    Split category string into category and sub-category. The category and sub-category
    are separated by a colon (":"). However, not all categories have sub-categories. This
    method handles both cases.

    Args:
        category (str): Category[:sub-category] String, e.g. "PROPERTY:VEHICLE", "PEOPLE"

    Returns:
        (category, sub_category)
    """
    try:
        (main_cat, sub_cat) = category.split(":", 2)
    except ValueError:
        (main_cat, sub_cat) = (category, None)

    if main_cat:
        main_cat = '/' + main_cat

    if sub_cat:
        sub_cat = '/' + sub_cat

    return (main_cat, sub_cat)


def next_available_request_number(requests: list) -> int:
    """
    Return the next available request number, which for us will be
    the highest number + 1.

    Args:
        requests (list): Existing discovery requests in a document.
    Returns:
        (int): The next available request number.
    """
    sorted_list = sorted(requests, key=itemgetter('number'))
    last_request = sorted_list[-1]
    return last_request['number'] + 1
