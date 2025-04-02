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
############################
spotipy_api_url = 'https://accounts.spotify.com/api/token'
spotipy_search_url = 'https://api.spotify.com/v1/search'
spotify_create_playlist_url = f'https://api.spotify.com/v1/users/'
spotify_user_authorization_url = 'https://accounts.spotify.com/authorize'
spotify_add_track_url = 'https://api.spotify.com/v1/playlists/'
spotify_username_url = 'https://api.spotify.com/v1/me'
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


def search_in_spotify(name, type, token):
    query = f'?q={name}&type={type}&limit=1'
    header = get_auth_header(token)
    search_url = spotipy_search_url + query
    response = requests.get(search_url, headers=header)
    if response.status_code == 200:
        search_res = json.loads(response.content)
        tar_result = search_res['tracks']['items'][0]
        return tar_result['id'], tar_result['name']


def add_tracks(playlist_id, tracks, token):
    url = spotify_add_track_url + f'{playlist_id}/tracks'
    headers = get_auth_header(token)
    headers.update({'Content-Type': 'application/json'})
    for idx in range(0, len(tracks), 100):
        block = tracks[idx: idx + 100]
        tracks = list(map(f'spotify:track:{tid}' for tid in block))
        data = {'uris': tracks}
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            pass


def get_user_authorization(session_id):
    user_auth_url = f'{spotify_user_authorization_url}?client_id={CLIENT_ID}&response_type=code&scope={scopes}&redirect_uri={redirect_url}&state={session_id}'
    webbrowser.open(user_auth_url)


def get_spotify_userid(token: str):
    headers = get_auth_header(token)
    response = requests.get(spotify_username_url, headers=headers)
    if response.status_code == 200:
        current_user = json.loads(response.content)
        user_id = current_user['id']
        return user_id


def spotify_playlist(playlist_name, mal_uname, token):
    current_uid = get_spotify_userid(token)
    header = get_auth_header(token)
    header.update({'Content-Type': 'application/json'})
    data = json.dumps({'name': playlist_name, 'description': f'{mal_uname}\'s Spotify PlayList', 'public': False})
    url = spotify_create_playlist_url + f'{current_uid}/playlists'
    response = requests.post(url, headers=header, data=data)
    if response.status_code == 200:
        result = json.loads(response.content)
        playlist_id = result['id']
        return playlist_id
