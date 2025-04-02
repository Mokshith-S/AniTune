import string
import time
import re
import aiohttp
import requests
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import uvicorn
from fastapi import FastAPI, status, Request
from fastapi.responses import JSONResponse
import asyncio
from dotenv import load_dotenv
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from exception_handler import AniException
from model import RangeModel
import math as m
from database import insert_, find_, DB_initialize, fetch_user_authcode, find_and_update
from spotify_module import search_in_spotify, generate_token, get_user_authorization, spotify_playlist, add_tracks
from fuzzywuzzy import fuzz
from uuid import uuid4

###################################################
load_dotenv("./access_key.env")
app = FastAPI()
exception = AniException()
# ani_memory = AniMemory()
DB_initialize().initialize(os.getenv('MONGO_DB'))

API_KEY = os.getenv("API_KEY")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_KEY = os.getenv("CLIENT_KEY")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
scope = "playlist-modify-public user-library-read"
redirect_url = "http://127.0.0.1:80/callback"

header = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "X-Request-With": "XMLHTTPRequest",
    "Host": "myanimelist.net",
    "TE": "trailers",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

mal_api_header = {
    'X-MAL-CLIENT-ID': API_KEY,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
}


####################################################

def retry_controller(times=5):
    def decorator(func):
        def wrapper(*args):
            req_retry = 0
            while req_retry < times:
                try:
                    return func(*args)
                except Exception as e:
                    req_retry += 1
                    print("retry triggered")
                    time.sleep(0.2 * req_retry)
            return func(*args)

        return wrapper

    return decorator


@retry_controller()
async def fetch_anime_details(url, session, idx):
    async with session.get(url, headers=mal_api_header) as response:
        if response.status == 200:
            res = await response.json()
            return res, idx


async def get_songs(anime_group: list):
    print("Extracting song id")

    async with aiohttp.ClientSession() as session:
        task = []
        for idx, anime in enumerate(anime_group):
            task.append(fetch_anime_details(
                f"https://api.myanimelist.net/v2/anime/{anime['anime_id']}?fields=title,opening_themes,ending_themes",
                session, idx))

            if len(task) == 3 or idx == len(anime_group) - 1:
                result = await asyncio.gather(*task)

                for ani_result, index in result:
                    song_titles = []
                    if ani_result:
                        for song_detail in ani_result.get("opening_themes", []):
                            song_info = song_detail.get("text")

                            sidx = song_info.find('"')
                            eidx = song_info[sidx + 1:].find('"')
                            name = song_info[sidx + 1: sidx + eidx + 1]
                            if not name.replace(' ', '').isalpha():
                                base_lang_sidx = name.find('(')
                                base_lang_eidx = name.find(')')
                                name = name[base_lang_sidx + 1: base_lang_eidx]

                            artist = song_info[sidx + eidx + 6:]
                            if '(' in artist:
                                base_artist_sidx = artist.find('(')
                                base_artist_eidx = artist.find(')')

                                holder = artist[base_artist_sidx + 1: base_artist_eidx]
                                if not 'ep' in holder:
                                    artist = holder
                                else:
                                    artist = artist[:base_artist_sidx]
                            name = name.translate(str.maketrans('', '', string.punctuation))
                            artist = artist.translate(str.maketrans('', '', string.punctuation))
                            song_titles.append({
                                'type': 'opening',
                                'song_name': name.strip(),
                                'artist_name': artist.strip()
                            })

                        for song_detail in ani_result.get("ending_themes", []):
                            song_info = song_detail.get("text")

                            sidx = song_info.find('"')
                            eidx = song_info[sidx + 1:].find('"')
                            name = song_info[sidx + 1: sidx + eidx + 1]
                            if not name.replace(' ', '').isalpha():
                                base_lang_sidx = name.find('(')
                                base_lang_eidx = name.find(')')
                                name = name[base_lang_sidx + 1: base_lang_eidx]

                            artist = song_info[sidx + eidx + 6:]
                            if '(' in artist:
                                base_artist_sidx = artist.find('(')
                                base_artist_eidx = artist.find(')')

                                holder = artist[base_artist_sidx + 1: base_artist_eidx]
                                if not 'ep' in holder:
                                    artist = holder
                                else:
                                    artist = artist[:base_artist_sidx]
                            name = name.translate(str.maketrans('', '', string.punctuation))
                            artist = artist.translate(str.maketrans('', '', string.punctuation))
                            song_titles.append({
                                'type': 'ending',
                                'song_name': name.strip(),
                                'artist_name': artist.strip()
                            })

                    anime_group[index].update({'songs': song_titles})
                task.clear()
    return anime_group


def generate_url(mal_user, offset, category_type):
    return fr"https://myanimelist.net/animelist/{mal_user}/load.json?offset={offset}&status={category_type}"


def authenticate():
    session = requests.Session()
    retry = Retry(connect=5, backoff_factor=0.5)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    sp = SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_KEY, scope=scope,
                      redirect_uri=redirect_url, requests_session=session)
    try:
        refresh_sp_frm_token = sp.refresh_access_token(REFRESH_TOKEN)
        access_point = spotipy.Spotify(auth=refresh_sp_frm_token["access_token"])
        print("Authenticated")
        return access_point
    except requests.exceptions.RequestException as e:
        raise exception.spotify_auth_exception(e)


def track_extractor(token, anime: dict):
    sname = anime['song_name']
    artist = anime['artist_name']
    track_id, song_name = search_in_spotify(sname, 'track', token)
    if fuzz.ratio(song_name, sname) > 90:
        anime.update({'track_id': track_id})
    else:
        anime.update({'track_id': None})
    return anime


def get_track_ids(sp, untraced_anime: list, workers=4):
    with ThreadPoolExecutor(max_workers=workers) as executor:
        processed = []
        track_cluster = []
        for index, untrace_sp_anime in enumerate(untraced_anime):
            track_cluster.clear()
            for idx in range(0, len(untrace_sp_anime['songs']), workers):
                sub_chunk = untrace_sp_anime['songs'][idx: idx + workers]
                track_cluster.extend(executor.map(track_extractor, [sp] * len(sub_chunk), sub_chunk))

            untrace_sp_anime.update({'songs': track_cluster})
            insert_(DB_initialize().get_collection('store'), untrace_sp_anime)
            processed.extend([x['track_id'] for x in untrace_sp_anime['songs'] if x['track_id']])

    return list(set(processed))


def create_playlist(sp, userid, playlist_name, playlist_desc, track_ids):
    playlist = sp.user_playlist_create(user=userid, name=playlist_name, description=playlist_desc, public=True,
                                       collaborative=False)
    playlist_id = playlist['id']
    for idx in range(0, len(track_ids), 100):
        track_grp = track_ids[idx:idx + 100]
        sp.playlist_add_items(playlist_id=playlist_id, items=track_grp)
    link = playlist["external_urls"]
    return playlist_id, link


async def delete_playlist(sp, time, playlist_id, uid):
    await asyncio.sleep(time)
    sp.user_playlist_unfollow(user=uid, playlist_id=playlist_id)
    print(f"Playlist {playlist_id} Deleted")


@app.get('/callback')
async def user_auth_endpoint(request: Request):
    session_id = request.query_params.get('state')
    auth_code = request.query_params.get('code')
    data = {
        'session_id': session_id,
        'auth': str(auth_code)
    }

    insert_(DB_initialize.get_collection('auth'), data)


@app.get('/authenticate')
async def verify():
    session_id = uuid4()
    get_user_authorization(session_id)


@app.post("/home")
async def home(ani_input: RangeModel):
    user_auth_code = fetch_user_authcode(DB_initialize.get_collection('auth'), ani_input.session_id)
    token, expire_time, refresh_token = generate_token(user_auth_code)
    find_and_update(DB_initialize.get_collection('auth'), ani_input.session_id, {
        'token': token,
        'expire': expire_time,
        'refresh_token': refresh_token
    })

    if ani_input.category_type < 0 and ani_input.category_type > 6:
        exception.category_exception()

    start = ani_input.anime_start
    target_amount = ani_input.anime_total
    total_fetches = m.ceil(target_amount / 200)
    target_anime_traced = []
    target_anime_untraced = []
    fetches = 0

    print("Fetching User Anime Collections")
    while fetches < total_fetches:
        url = generate_url(ani_input.mal_user_name, start + (fetches * 200), ani_input.category_type)
        response = requests.get(url, headers=header)

        if response.status_code == 200:
            ani_data = response.json()

            if len(ani_data) == 0:
                if fetches == 0:
                    exception.empty_category_exception(
                        ["All Anime", "Watching", "Completed", "On Hold", "Dropped", "Plan to Watch"][
                            ani_input.category_type])
                break

            for anime_entry in ani_data[:target_amount - (len(target_anime_traced) + len(target_anime_untraced))]:
                id = anime_entry.get("anime_id")
                search_result = find_(DB_initialize().get_collection('store'), id)
                if search_result:
                    songs = search_result['songs']
                    tracks = [x['track_id'] for x in songs if x['track_id']]
                    target_anime_traced.extend(tracks)
                else:
                    target_anime_untraced.append({
                        'anime_id': id,
                        'title': anime_entry['anime_title'],
                        'title_eng': anime_entry['anime_title_eng'],
                    })

        fetches += 1

    new_traced_anime = await get_songs(target_anime_untraced)
    processed_anime = get_track_ids(token, new_traced_anime)
    target_anime_traced.extend(processed_anime)
    if not ani_input.playlist_name:
        playlist_name = str(uuid4())
    else:
        playlist_name = ani_input.playlist_name

    pl_id = spotify_playlist(playlist_name, ani_input.mal_user_name, token)
    add_tracks(pl_id, target_anime_traced, token)


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True, port=80, host="127.0.0.1")

'''
###########################TODO##############################
1) Go with mongodb to store {anime ID : spotify song link} (use anime ID instead anime song ID)
2) Remove anime ID that are present in db before pass the collection of anime IDs
3) Pinpoint search on spotify, if not found skip the song
4) Find better way delete the playlists

###########################EXTRA##############################
1) Implement the same for youtube
'''
