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

load_dotenv("./access_key.env")

app = FastAPI()
exception = AniException()
ani_memory = AniMemory()

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


async def fetch_anime_details(url, session):
    async with session.get(url, headers=mal_api_header) as response:
        if response.status == 200:
            return await response.json()


async def get_songs(anime_ids: list):
    print("Extracting song id")
    anime_lib = set()
    processed_anime_id = 0

    async with aiohttp.ClientSession() as session:
        while processed_anime_id <= len(anime_ids):
            task = [fetch_anime_details(
                f"https://api.myanimelist.net/v2/anime/{aid}?fields=title,opening_themes,ending_themes", session) for
                aid in anime_ids[processed_anime_id:processed_anime_id + 3]]
            result = await asyncio.gather(*task)
            print("." * len(result), end="")

            for ani_result in result:
                for song_detail in ani_result.get("opening_themes", []):
                    song_name = song_detail.get("text")
                    song_id = song_detail.get("id")

                    if ani_memory.check_memory(song_id):
                        continue

                    if "ep" in song_name or "eps" in song_name:
                        eps_start = song_name.find("ep")
                        eps_end = song_name[eps_start:].find(")") + eps_start
                        song_name = song_name[:eps_start - 1] + song_name[eps_end + 1:]

                    title = re.sub("^#[0-9]+:|\"", "", song_name)
                    anime_lib.add([song_id, title.strip()])

                for song_detail in ani_result.get("ending_themes", []):
                    song_name = song_detail.get("text")
                    song_id = song_detail.get("id")

                    if ani_memory.check_memory(song_id):
                        continue

                    if "eps" in song_name or "ep" in song_name:
                        eps_start = song_name.find("ep")
                        eps_end = song_name[eps_start:].find(")") + eps_start
                        song_name = song_name[:eps_start - 1] + song_name[eps_end + 1:]

                    title = re.sub("^#[0-9]+:|\"", "", song_name)
                    anime_lib.add([song_id, title.strip()])

            processed_anime_id += 3
    return list(anime_lib)


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

def track_extractor(sp, song_info: list):
    print("-", end="")
    result = sp.search(q=song_info[1], limit=1, type="track")
    tracks = result['tracks']['items']
    if tracks:
        return [song_info[0], tracks[0]['id']]
    else:
        return None

def get_track_ids(sp, s_names: list):
    track_ids = []
    song_counter = 0
    with ThreadPoolExecutor(max_workers=3) as executor:
        while song_counter <= len(s_names):
            track_cluster = executor.map(track_extractor, [sp] * 3, s_names[song_counter : song_counter + 3])

            for track in track_cluster:
                if track:
                    track_ids.append(track[1])
            song_counter += 3
    return track_ids


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
    if 0 < ani_input.category_type and ani_input.category_type > 6:
        exception.category_exception()

    start = ani_input.anime_start
    target_amount = ani_input.anime_total
    total_fetches = m.ceil(target_amount / 200)
    anime_processed = 0
    anime_id_list = []
    fetches = 0

    print("Fetching User Anime Collections")
    while fetches <= total_fetches:
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

            for anime_entry in ani_data:
                anime_id_list.append(anime_entry.get("anime_id"))
                anime_processed += 1
                if anime_processed == target_amount:
                    break

        fetches += 1
        time.sleep(0.5)

    anime_song_collection = await get_songs(anime_id_list)

    print("Extracted All Required Songs")
    spotify_access = authenticate()
    track_ids = get_track_ids(spotify_access, anime_song_collection)
    print("Extract Song Track Id")
    userid = spotify_access.current_user()["id"]
    playlist_name = str(uuid4())
    playlist_desc = ("Listen to your favourite anime songs")
    play_id, link = create_playlist(spotify_access, userid, playlist_name, playlist_desc, track_ids)
    print(f"Created Playlist {playlist_name}")
    asyncio.create_task(delete_playlist(spotify_access, 300, play_id, userid))
    print("Initiated Playlist Deletion")
    response_body = {"Playlist_link": link}
    return JSONResponse(content=response_body, status_code=status.HTTP_200_OK)


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True, port=80, host="127.0.0.1")
