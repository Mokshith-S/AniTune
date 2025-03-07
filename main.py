import time
import re
import aiohttp
import requests
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import uvicorn
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
import asyncio
from dotenv import load_dotenv
from uuid import uuid4
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from exception_handler import AniException
from model import RangeModel
import math as m
from ani_getter import AniMemory
from database import insert_, find_, DB_initialize
from spotify_module import search_, generate_token
from fuzzywuzzy import fuzz
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
            task.append(fetch_anime_details(f"https://api.myanimelist.net/v2/anime/{anime['anime_id']}?fields=title,opening_themes,ending_themes", session, idx))

            if len(task) == 3 or idx == len(anime_group) - 1:
                result = await asyncio.gather(*task)

                for ani_result, index in result:
                    if ani_result:
                        song_titles = []
                        for song_detail in ani_result.get("opening_themes", []):
                            song_name = song_detail.get("text")

                            if "ep" in song_name or "eps" in song_name:
                                eps_start = song_name.find("ep")
                                eps_end = song_name[eps_start:].find(")") + eps_start
                                song_name = song_name[:eps_start - 1] + song_name[eps_end + 1:]

                            title = re.sub("^#[0-9]+:|\"", "", song_name)
                            song_titles.append(title.strip())
                        anime_group[index].update({'opening_theme_names': song_titles})
                        song_titles.clear()

                        for song_detail in ani_result.get("ending_themes", []):
                            song_name = song_detail.get("text")

                            if "eps" in song_name or "ep" in song_name:
                                eps_start = song_name.find("ep")
                                eps_end = song_name[eps_start:].find(")") + eps_start
                                song_name = song_name[:eps_start - 1] + song_name[eps_end + 1:]

                            title = re.sub("^#[0-9]+:|\"", "", song_name)
                            song_titles.append(title.strip())
                        anime_group[index].update({'ending_theme_names': song_titles})
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


def track_extractor(sp, song_info: str):
    eidx = song_info[1:].find('"')
    name = song_info[1:eidx+1]
    if not name.replace(' ', '').isalpha():
        base_lang_sidx = name.find('(')
        base_lang_eidx = name.find('(')
        name = name[base_lang_sidx: base_lang_eidx+1]

    artist = song_info[eidx+5:]
    if '(' in artist:
        base_artist_sidx = artist.find('(')
        base_artist_eidx = artist.find(')')

        holder = artist[base_artist_sidx: base_artist_eidx+1]
        if not 'ep' in holder:
            artist = holder
    track_id, song_name = search_(name, 'track', sp)
    if fuzz.ratio(song_name, name) > 90:
        return {name: track_id}
    else:
        return None



def get_track_ids(sp, untraced_anime: list, workers=4):
    with ThreadPoolExecutor(max_workers=workers) as executor:
        chunk = []
        processed = []
        for index, untrace_sp_anime in enumerate(untraced_anime):
            chunk.extend(untrace_sp_anime['opening_theme_names'])
            chunk.extend(untrace_sp_anime['ending_theme_names'])

            for idx in range(0, len(chunk), workers):
                track_cluster = executor.map(track_extractor, [sp] * len(chunk), chunk)

            processed.append(untrace_sp_anime.update({'spotify_track_id': track_cluster}))
            insert_(DB_initialize().get_collection(), untrace_sp_anime)
            chunk.clear()

        # while song_counter < len(titles):
        #     id = ids[song_counter]
        #     name = titles[song_counter]
        #
        #     if not ani_memory.check_memory(id):
        #         ids_chunk.append(id)
        #         chunk.append(name)
        #     else:
        #         track = ani_memory.get_song_track(id)
        #         track_ids.append(track)
        #         print("#", end="")
        #
        #     if len(chunk) == 3 or song_counter == len(s_collection) - 1:
        #         track_cluster = executor.map(track_extractor, [sp] * len(chunk), chunk)
        #
        #         for id, track in zip(ids_chunk, track_cluster):
        #             if track:
        #                 track_ids.append(track)
        #             ani_memory.add_song_memory(id, track)
        #         chunk.clear()
        #         ids_chunk.clear()
        #
        #     song_counter += 1
    # ani_memory.save()
    return processed


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


@app.post("/home")
async def spotPlaylist(ani_input: RangeModel):
    if ani_input.category_type < 0 and ani_input.category_type > 6:
        exception.category_exception()

    start = ani_input.anime_start
    target_amount = ani_input.anime_total
    total_fetches = m.ceil(target_amount / 200)
    anime_processed = 0
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

            for anime_entry in ani_data[:target_amount - (len(target_anime_traced)+len(target_anime_untraced))]:
                id = anime_entry.get("anime_id")
                if find_(DB_initialize().get_collection(), id, 'status'):
                    target_anime_traced.append(find_(DB_initialize().get_collection(), id, 'value'))
                else:
                    target_anime_untraced.append({
                        'anime_id': id,
                        'title': anime_entry['anime_title'],
                        'title_eng': anime_entry['anime_title_eng'],
                    })



        fetches += 1
        # time.sleep(0.5)

    new_traced_anime = await get_songs(target_anime_untraced)

    print("Extracted All Required Songs")
    spotify_access = authenticate()
    # spotify_access = generate_token()
    processed_anime = get_track_ids(spotify_access, new_traced_anime)
    response = target_anime_traced + processed_anime
    track_id = []
    for res in response:
        track_id.extend(res.get('spotify_track_id'))
    print("Extract Song Track Id")
    userid = spotify_access.current_user()["id"]
    playlist_name = str(uuid4())
    playlist_desc = ("Listen to your favourite anime songs")
    play_id, link = create_playlist(spotify_access, userid, playlist_name, playlist_desc, track_id)
    print(f"Created Playlist {playlist_name}")
    asyncio.create_task(delete_playlist(spotify_access, 300, play_id, userid))
    print("Initiated Playlist Deletion")
    response_body = {"Playlist_link": link}
    return JSONResponse(content=response_body, status_code=status.HTTP_200_OK)


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

