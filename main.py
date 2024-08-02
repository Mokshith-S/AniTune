import json

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import asyncio
import aiohttp
from dotenv import load_dotenv
from uuid import uuid4
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from jikanpy.exceptions import JikanException

from exception_handler import AniException
from ani_getter import AniGetter
from model import InputModel, RangeModel

load_dotenv("./access_key.env")

app = FastAPI()

exception = AniException()

aniTuneLibrary = set()

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
        elif response.status == 500:
            return None


async def get_songs(anime_ids: list, limit):
    print("Extracting song id")
    urls_to_process = 0
    global aniTuneLibrary

    async with aiohttp.ClientSession() as session:
        while urls_to_process <= len(anime_ids):
            urls = list(map(lambda
                                ani_id: f'https://api.myanimelist.net/v2/anime/{ani_id}?fields=title,opening_themes,ending_themes',
                            anime_ids[urls_to_process: urls_to_process + 3]))
            urls_to_process += 3
            tasks = [fetch_anime_details(url, session) for url in urls]
            result = await asyncio.gather(*tasks)
            for res in result:
                for song_detail in res.get("opening_themes", []):
                    if len(aniTuneLibrary) != limit:
                        song_name = song_detail.get("text").split("\"")[1]
                        song_name += song_detail.get("text").split("\"")[2].split("(")[0]
                        aniTuneLibrary.add(song_name.strip())
                    else:
                        return 0

                for song_detail in res.get("ending_themes", []):
                    if len(aniTuneLibrary) != limit:
                        aniTuneLibrary.add(song_detail.get("text").split("\"")[1])
                    else:
                        return 0

    if len(aniTuneLibrary) < limit:
        return 1
    return 0


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
        print(f"Failed Authentication -- {e}")
        return None


def get_track_ids(sp, s_names: set):
    track_ids = []
    while len(s_names) != 0:
        song = s_names.pop()
        result = sp.search(q=song, limit=1, type="track")
        tracks = result['tracks']['items']
        if tracks:
            # print(tracks[0]["id"])
            track_ids.append(tracks[0]['id'])
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


@app.get("/home")
async def get_anime_list(user_input: InputModel):
    if user_input.mal_user_name is None:
        exception.user_field_empty_exception()

    try:
        aniHunter = AniGetter(user_input.mal_user_name)
        user_stats = aniHunter.user_statistics()
        mapped_stats = json.dumps({
            "All Animes": user_stats[0],
            "Watching": user_stats[1],
            "Completed": user_stats[2],
            "On Hold": user_stats[3],
            "Dropped": user_stats[4],
            "Plan to Watch": user_stats[5]
        })
        return JSONResponse(content=mapped_stats)
    except JikanException:
        exception.user_exception(user_input.mal_user_name)


@app.post("/fetch")
async def spotPlaylist(ani_input: RangeModel):
    if 0 < ani_input.category_type and ani_input.category_type > 6:
        exception.category_exception()

    controller = 1
    offset = 0

    while controller == 1:
        url = generate_url(ani_input.mal_user_name, offset, ani_input.category_type)
        response = requests.get(url, headers=header)
        print("Fetching User Anime Collections")
        if response.status_code == 200:
            ani_data = response.json()
            if len(ani_data) == 0:
                break
            anime_list = list(map(lambda anime: anime.get("anime_id"), ani_data))
            controller = await get_songs(anime_list, ani_input.song_limit)
        offset += 200
    print("Extracted All Required Songs")
    spotify_access = authenticate()
    if spotify_access is None:
        return JSONResponse(content={"body": "Spotify Auth Error"})
    track_ids = get_track_ids(spotify_access, aniTuneLibrary)
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
