from pymongo import MongoClient
from dotenv import load_dotenv
import os
from exception_handler import DB_Exception

#############################################
db_excep = DB_Exception()


class DB_initialize:
    mongo_connect = None
    mongo_db = None
    ani_detail = None
    auths = None

    @staticmethod
    def initialize(connection_url: str):
        DB_initialize.mongo_connect = MongoClient(connection_url)
        DB_initialize.mongo_db = DB_initialize.mongo_connect['AniTune']
        DB_initialize.ani_detail = DB_initialize.mongo_db['AniLibrary']
        DB_initialize.auths = DB_initialize.mongo_db['Spotify_auth']

    @staticmethod
    def get_db():
        if DB_initialize.mongo_db is None:
            db_excep.db_exception()
        else:
            return DB_initialize.mongo_db

    @staticmethod
    def get_collection(type: str):
        if type == 'store':
            if DB_initialize.ani_detail is None:
                db_excep.collection_exception()
            return DB_initialize.ani_detail
        elif type == 'auth':
            return DB_initialize.auths


#############################################

def insert_(records, anime_info: dict):
    records.insert_one(anime_info)


def find_(records, anime_id: int):
    atune = records.find_one({'anime_id': anime_id})
    return atune


def fetch_user_authcode(records, session_id: str):
    auth = records.find_one({'session_id': session_id})
    return auth['auth']


def find_and_update(records, session_id: str, data: dict):
    records.update_one({'session_id': session_id},
                       {'$set': data})


if __name__ == '__main__':
    db = DB_initialize("mongodb://localhost:27017/")
    insert_(db, {'a': 134})
