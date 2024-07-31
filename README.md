# AniTune API

AniTune API allows MyAnimeList users to convert their saved anime into a Spotify playlist. By providing your MyAnimeList
username, the number of songs, and an anime category, you can create a custom Spotify playlist featuring opening and
ending themes from the anime in your profile.

## Features

Retrieve Anime Songs: Extract opening and ending themes from your MyAnimeList anime list.

Create Spotify Playlists: Automatically generate a Spotify playlist from the extracted songs.

Customizable: Specify the number of songs and anime category for playlist creation.

Automatic Playlist Deletion: The playlist will be automatically deleted after a specified time (5 minutes by default).

## API Endpoints

GET /home

Parameters:

mal_user_name (string, required): MyAnimeList username. <br/>
song_limit (int, optional): Number of songs to be included in the playlist (default is 100). <br/>
category_type (int, optional): Category of anime in your MyAnimeList profile (default is 1). <br/>

0: All Anime <br/>
1: Watching <br/>
2: Completed <br/>
3: On Hold <br/>
4: Dropped <br/>
6: Plan to Watch <br/>

Response: <br/>
Returns a JSON response with the Spotify playlist link.