import requests
import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import asyncio
import aiohttp
from typing import Union, Optional
from dotenv import load_dotenv
from uuid import uuid4
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv("./access_key.env")

app = FastAPI()

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


class InputModel(BaseModel):
    mal_user_name: str = Field(default=None)
    song_limit: int = Field(default=100)
    category_type: int = Field(default=1)


async def fetch_anime_details(url, session):
    async with session.get(url, headers=mal_api_header) as response:
        if response.status == 200:
            return await response.json()
        elif response.status == 500:
            return None


async def get_songs(anime_ids: list, limit):
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
    sp = SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_KEY, scope=scope,
                      redirect_uri=redirect_url)
    refresh_sp_frm_token = sp.refresh_access_token(REFRESH_TOKEN)
    access_point = spotipy.Spotify(auth=refresh_sp_frm_token["access_token"])
    return access_point


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
    sp.playlist_add_items(playlist_id=playlist_id, items=track_ids)
    print(playlist["external_urls"])
    return playlist_id


async def delete_playlist(sp, time, playlist_id, uid):
    await asyncio.sleep(time)
    await sp.user_playlist_unfollow(user=uid, playlist_id=playlist_id)


def perform_delayed_tasks(sp, time, play_id, userid):
    asyncio.create_task(delete_playlist(sp, time, play_id, userid))


@app.get("/")
async def get_anime_list(ani_input: InputModel):
    if ani_input.mal_user_name is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {ani_input.mal_user_name} not found")
    if 0 > ani_input.category_type or ani_input.category_type > 6:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid category")
    controller = 1
    offset = 0

    while controller == 1:
        url = generate_url(ani_input.mal_user_name, offset, ani_input.category_type)
        response = requests.get(url, headers=header)
        if response.status_code == 200:
            ani_data = response.json()
            if len(ani_data) == 0:
                break
            anime_list = list(map(lambda anime: anime.get("anime_id"), ani_data))
            controller = asyncio.run(get_songs(anime_list, ani_input.song_limit))
        offset += 200

    spotify_access = authenticate()
    track_ids = get_track_ids(spotify_access, aniTuneLibrary)
    userid = spotify_access.current_user()["id"]
    playlist_name = str(uuid4())
    playlist_desc = "Message"
    play_id = create_playlist(spotify_access, userid, playlist_name, playlist_desc, track_ids)
    asyncio.run(perform_delayed_tasks(spotify_access, 300, play_id, userid))


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True, port=80, host="127.0.0.1")
