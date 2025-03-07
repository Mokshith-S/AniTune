from pymongo import MongoClient
from dotenv import load_dotenv
import os
from exception_handler import DB_Exception
#############################################
db_excep = DB_Exception()
class DB_initialize:
    mongo_connect = None
    mongo_db = None
    mongo_collection = None

    @staticmethod
    def initialize(connection_url):
        if not DB_initialize.mongo_connect:
            DB_initialize.mongo_connect = MongoClient(connection_url)
            DB_initialize.mongo_db = DB_initialize.mongo_connect['AniTune']
            DB_initialize.mongo_collection = DB_initialize.mongo_db['AniLibrary']

    @staticmethod
    def get_db():
        if DB_initialize.mongo_db is None:
            db_excep.db_exception()
        else:
            return DB_initialize.mongo_db

    @staticmethod
    def get_collection():
        if DB_initialize.mongo_collection is None:
            db_excep.collection_exception()
        else:
            return DB_initialize.mongo_collection


#############################################

def insert_(records, anime_info: dict):
    records.insert_one(anime_info)

def find_(records, anime_id: int, mode='value'):
    atune = records.find_one({'aid': anime_id})
    if mode == 'status':
        return bool(atune)
    if mode == 'value':
        return {
            'opening': atune['opening'],
            'ending': atune['ending']
        }

if __name__ == '__main__':
    db = DB_initialize("mongodb://localhost:27017/")
    insert_(db, {'a':134})
