import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Union, Optional

app = FastAPI()
API_KEY = "e5f2c3bc5c08d853346a559303fb3127"
header = {
    "Accept" : "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding" : "gzip, deflate, br, zstd",
    "Accept-Language" : "en-US,en;q=0.5",
    "Connection" : "keep-alive",
    "User-Agent" : "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "X-Request-With" : "XMLHTTPRequest",
    "Host" : "myanimelist.net",
    "TE" : "trailers",
    "Sec-Fetch-Dest" : "empty",
    "Sec-Fetch-Mode" : "cors",
    "Sec-Fetch-Site" : "same-origin",
}

class InputModel(BaseModel):
    mal_user_name : str = Field(default=None)
    song_limit : int = Field(default=100)


async def get_songs(anime_ids: list):
    ...

@app.get("/")
def get_anime_list(ani_input: InputModel):
    if ani_input.mal_user_name is None:
        raise HTTPException(status_code=404, detail=f"User {ani_input.mal_user_name} not found")
    url = fr"https://myanimelist.net/animelist/{ani_input.mal_user_name}/load.json?offset=0&status=1"
    response = requests.get(url,headers=header)
    if response.status_code == 200:
        anime_list = {"anime_ids" : list(map(lambda anime: anime.get("anime_id"), response.json()))}
        return anime_list

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
# if __name__ == "__main__":
#     uvicorn.run("main:app", reload=True, port=80, host="127.0.0.1")

if __name__ == '__main__':
    exec()