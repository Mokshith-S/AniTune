import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import asyncio
import aiohttp
from typing import Union, Optional
from dotenv import load_dotenv
import os

load_dotenv("./ani_key.env")

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


async def fetch_anime_details(url, session):
    async with session.get(url, header=mal_api_header) as response:
        return response.json()


async def get_songs(anime_ids: list):
    concrt_prc_rng = 0
    async with aiohttp.ClientSession() as session:
        while concrt_prc_rng <= len(anime_ids):
            urls = list(map(lambda
                                ani_id: f'https://api.myanimelist.net/v2/anime/{ani_id}?fields=title,opening_themes,ending_themes',
                            anime_ids[concrt_prc_rng: concrt_prc_rng + 3]))

            tasks = [fetch_anime_details(url, session) for url in urls]
            result = await asyncio.gather(*tasks)
            for res in result:
                aniTuneLibrary[res.get("id")] = {
                    "title": res.get("title"),
                    "opening": [{"op_sng": song.get("text").split("\\")[1]} for song in res.get("opening_themes")],
                    "ending": [{"en_sng": song.get("text").split("\\")[1]} for song in res.get("ending_themes")]
                }
                concrt_prc_rng += len(res.get("opening_themes")) + len(res.get("ending_themes"))


@app.get("/")
def get_anime_list(ani_input: InputModel):
    if ani_input.mal_user_name is None:
        raise HTTPException(status_code=404, detail=f"User {ani_input.mal_user_name} not found")
    url = fr"https://myanimelist.net/animelist/{ani_input.mal_user_name}/load.json?offset=0&status=1"
    response = requests.get(url, headers=header)
    if response.status_code == 200:
        anime_list = list(map(lambda anime: anime.get("anime_id"), response.json()))
        asyncio.run(get_songs(anime_list))


def exec():
    data = {}
    mal_api_header = {
        'X-MAL-CLIENT-ID': API_KEY,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    }
    ani_id = 1
    url = f'https://api.myanimelist.net/v2/anime/{ani_id}?fields=title,opening_themes,ending_themes'

    response = requests.get(url, headers=mal_api_header)
    if response.status_code == 200:
        data = response.json()
    data


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True, port=80, host="127.0.0.1")

# if __name__ == '__main__':
#     exec()
