import os
from dotenv import load_dotenv
import base64
import requests
import json
import webbrowser
#############################
load_dotenv(r'.\access_key.env')
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_KEY = os.getenv("CLIENT_KEY")
SPOTIFY_USER = os.getenv("SPOTIFY_USER")
############################
spotipy_api_url = 'https://accounts.spotify.com/api/token'
spotipy_search_url = 'https://api.spotify.com/v1/search'
spotify_create_playlist_url = f'https://api.spotify.com/v1/users/{SPOTIFY_USER}/playlists'
spotify_user_authorization_url = 'https://accounts.spotify.com/authorize'
redirect_url = "http://127.0.0.1:80/callback"
#############################
scopes = "playlist-modify-private playlist-modify-public"
#############################

def generate_token(auth_code, refresh_token=None):
    auth_string = CLIENT_ID + ":" + CLIENT_KEY
    auth_base64 = base64.b64encode(auth_string.encode()).decode()

    header = {
        "Authorization": "Basic " + auth_base64,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    if refresh_token:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
    else:
        # data = {'grant_type': 'client_credentials'}
        data = {
                'grant_type': 'authorization_code',
                'code': auth_code,
                'redirect_uri': redirect_url
            }
    response = requests.post(spotipy_api_url, headers=header, data=data)
    if response.status_code == 200:
        access_token = json.loads(response.content)
        token = access_token['access_token']
        refresh_token = access_token['refresh_token']
        expire_time = access_token['expires_in']

        return token, expire_time, refresh_token

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

def get_user_authorization(session_id):
    user_auth_url = f'{spotify_user_authorization_url}?client_id={CLIENT_ID}&response_type=code&scope={scopes}&redirect_uri={redirect_url}&state={session_id}'
    webbrowser.open(user_auth_url)

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