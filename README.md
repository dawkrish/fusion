## Fusion : Convert playlists between Spotify & YouTubeMusic 

We use Spotify API & YouTube API extensively for this project

As there is no dedicated API for YouTube Music, we use YouTube API

Firstly we need to get access tokens for both authorizations to do anything

Each playlist in YTM is also a playlist of YT, the only difference is of the domain

Example 

Playlist ID - 123456

* For YT -> https://www.youtube.com/playlist?list=`123456`
* For YTM -> https://music.youtube.com/playlist?list=`123456`

So essentially we create a playlist in the YouTube account and the same playlist is used for YouTube Music account

### Spotify to YouTube Music
* First we ask for Spotify playlist-id and then we make a request to Spotify API to get all the songs. Then we form a `song-artist(s)` attribute for each song and save it. We also extract playlist name
* Its time that we use the search endpoint of YouTube API. We search each `song-artist(s)` attribute and get the top result's `videoId`
* We create a playlist by YouTube API with the extracted playlist name
* We insert the songs(videoId) in the newly created playlist.

### Same process is for YouTube Music to Spotify with some slight changes 

This app is made in python with the `Flask` framework which helps up spinning a server, storing access tokens, route matching and etc.
