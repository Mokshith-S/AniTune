import requests
import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import asyncio
import aiohttp
from typing import Union, Optional
from dotenv import load_dotenv
import os

load_dotenv("./access_key.env")

app = FastAPI()

aniTuneLibrary = dict()

API_KEY = os.getenv("API_KEY")
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
        return await response.json()


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
                    aniTuneLibrary[song_detail.get("id")] = song_detail.get("text").split("\"")[1]

                for song_detail in res.get("ending_themes", []):
                    aniTuneLibrary[song_detail.get("id")] = song_detail.get("text").split("\"")[1]

                aniTuneExtracted = len(aniTuneLibrary)

                if aniTuneExtracted > limit:
                    tmp = {k: aniTuneLibrary[k] for k in list(aniTuneLibrary.keys())[:100]}
                    aniTuneLibrary = tmp
                    break
                elif aniTuneExtracted == limit:
                    break
    if len(aniTuneLibrary) < limit:
        return 1
    return 0


def generate_url(mal_user, offset, category_type):
    return fr"https://myanimelist.net/animelist/{mal_user}/load.json?offset={offset}&status={category_type}"


@app.get("/")
def get_anime_list(ani_input: InputModel):
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
    return aniTuneLibrary


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True, port=80, host="127.0.0.1")
