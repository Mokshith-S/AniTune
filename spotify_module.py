import os
from dotenv import load_dotenv
import base64
import requests
import json
#############################
load_dotenv(r'.\access_key.env')
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_KEY = os.getenv("CLIENT_KEY")
SPOTIFY_USER = os.getenv("SPOTIFY_USER")
############################
spotipy_api_url = 'https://accounts.spotify.com/api/token'
spotipy_search_url = 'https://api.spotify.com/v1/search'
spotify_create_playlist_url = f'https://api.spotify.com/v1/users/{SPOTIFY_USER}/playlists'
# spotify_user_url = 'https://api.spotify.com/v1/me'
#############################

def generate_token():
    auth_string = CLIENT_ID + ":" + CLIENT_KEY
    auth_bytes = auth_string.encode('utf-8')
    auth_base64 = str(base64.b64encode(auth_bytes), 'utf-8')

    header = {
        "Authorization": "Basic " + auth_base64,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {'grant_type': 'client_credentials'}
    response = requests.post(spotipy_api_url, headers=header, data=data)
    if response.status_code == 200:
        access_token = json.loads(response.content)
        return access_token['access_token']

def get_auth_header(token):
    return {'Authorization': 'Bearer ' + token}

def search_(search_string, type, token):
    query = f'?q={search_string}&type={type}&limit=1'
    header = get_auth_header(token)
    search_url = spotipy_search_url + query
    response = requests.get(search_url, headers=header)
    if response.status_code == 200:
        search_res = json.loads(response.content)
        tar_result = search_res['tracks']['items'][0]
        return tar_result['id'], tar_result['name']

def get_current_user():
    ...

def spotify_playlist(playlist_name, mal_uname, token):
    header = get_auth_header(token)
    header.update({'Content-Type': 'application/json'})
    data = json.dumps({'name': playlist_name, 'description': f'{mal_uname}\'s Spotify PlayList', 'public': False})
    response = requests.post(spotify_create_playlist_url, headers=header, data=data)
    if response.status_code == 200:
        result = json.loads(response.content)


if __name__ == '__main__':
    spotify_at = generate_token()
    # spotify_token = search_("無心拍数", 'track', spotify_at)
    spotify_playlist('sdfdsf', 'sdfsdf', spotify_at)