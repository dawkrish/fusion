import base64
from datetime import timedelta

import requests as re
import requests.packages

from ytmusicapi import YTMusic
from flask import Flask, render_template, request, session, redirect

app = Flask(__name__)
yt = YTMusic()
app.secret_key = 'the random string'
app.permanent_session_lifetime = timedelta(minutes=60)

# SPOTIFY_REDIRECT_URI = "http://localhost:5000/spotify/redirect/"
SPOTIFY_REDIRECT_URI = "https://dawkrish.pythonanywhere.com/spotify/redirect/"
SPOTIFY_CLIENT_ID = "408169d94bb04fa5976224d191be1d80"
SPOTIFY_CLIENT_SECRET = "89dd40939ccf4c64800be659891e9884"
SPOTIFY_SCOPE = "user-read-private user-read-email playlist-modify-public"

# YTM_REDIRECT_URI = "http://localhost:5000/ytm/redirect/"
YTM_REDIRECT_URI = "https://dawkrish.pythonanywhere.com/ytm/redirect/"
YTM_CLIENT_ID = "1041717439867-5pdrdovtic52i0l7ec31p44jsdi1hfop.apps.googleusercontent.com"
YTM_CLIENT_SECRET = "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"
YTM_SCOPE = "https://www.googleapis.com/auth/youtube"


@app.route("/privacy-policy")
def privacy_policy():
    return render_template("privacy_policy.html")


@app.route("/terms-services")
def terms_services():
    return render_template("terms_services.html")


@app.route('/')
def hello_world():
    # print(session)
    data = {
        "spotify_redirect_url": spotify_generate_redirect_string(SPOTIFY_CLIENT_ID, SPOTIFY_SCOPE,
                                                                 SPOTIFY_REDIRECT_URI),
        "ytm_redirect_url": ytm_generate_redirect_string(YTM_CLIENT_ID, YTM_SCOPE, YTM_REDIRECT_URI)
    }
    return render_template("index.html", data=data)


@app.route("/spotify/redirect/")
def spotify_redirect_route():
    authorization_code = request.args.get("code")
    access_token = spotify_access_token(authorization_code)
    session["spotify_access_token"] = access_token
    session["user_id"] = spotify_authorized_user_id()
    return redirect("/")


@app.route("/ytm/redirect/")
def ytm_redirect_route():
    code = request.args.get("code")
    print("authorziation code -> ", code)
    access_token = ytm_access_token(code)
    session["ytm_access_token"] = access_token
    return redirect("/")


@app.route("/ytmusic-to-spotify", methods=["GET", "POST"])
def ytmuscic_to_spotify():
    print("-------------------DO WE COME HERE DO WE COME HERE AT ytmusic-to-spotify GET-------------------")
    if request.method == "GET":
        return render_template("ytmusic-to-spotify.html")

    print("-------------------DO WE COME HERE DO WE COME HERE AT ytmusic-to-spotify POST-------------------")
    link = request.form["ytm-link"]
    playlist_title, playlist_description, playlist_tracks = ytm_get_playlist_info(link)
    if playlist_title is None or playlist_description is None or playlist_tracks is None:
        return "this is wrong playlist ID, go back"

    print("----------------------------")
    print(playlist_title, playlist_description)
    titles = []
    for t in playlist_tracks:
        title_artist = ""
        title_artist += t["snippet"]["title"]
        title_artist += "-"
        title_artist += t["snippet"]["description"][:15]
        titles.append(title_artist)

    spotify_songs = []
    for t in titles:
        s = spotify_search_song(t)
        if s is None:
            return redirect("/")
        spotify_songs.append(s)

    created_playlist_id = spotify_create_playlist(playlist_title, playlist_description)
    if created_playlist_id is None:
        return redirect("/")
    if spotify_add_songs_to_playlist(created_playlist_id, spotify_songs) is None:
        return redirect("/")

    data = {
        "link": "https://open.spotify.com/playlist/" + created_playlist_id
    }
    return render_template("spotify_playlist_created.html", data=data)


@app.route("/spotify-to-ytmusic", methods=["GET", "POST"])
def spotify_to_ytmusic():
    if request.method == "GET":
        return render_template("spotify-to-ytmusic.html")
    link = request.form["spotify-link"]
    print("----------------" + link)
    resp = spotify_hit_api("/playlists/" + link, method="GET")
    if resp is None:
        return redirect("/")
    if not resp.ok:
        return "This playlist ID is invalid, go back and try another one!"

    resp = resp.json()
    playlist_name = resp["name"]
    playlist_description = resp["description"]
    titles = []
    tracks = resp["tracks"]["items"]
    for t in tracks:
        title = t["track"]["name"]
        title += " "
        for a in t["track"]["artists"]:
            title += a["name"]
            title += ","
        titles.append(title)

    ytm_songs = []
    for t in titles:
        ytm_songs.append(ytm_search_song(t))

    print(ytm_songs)

    headers = {
        "Authorization": "Bearer " + session.get("ytm_access_token")
    }
    body = {
        "snippet": {
            "title": playlist_name,
            "description": playlist_description
        },
        "status": {
            "privacyStatus": "public"
        }
    }
    req = re.post("https://www.googleapis.com/youtube/v3/playlists?part=snippet,status", json=body, headers=headers)
    if not req.ok:
        print(req.text)
        session.pop("ytm_access_token")
        return redirect("/")
    resp = req.json()
    created_playlist_id = resp["id"]

    for song in ytm_songs:
        body = {
            "snippet": {
                "playlistId": created_playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": song
                }

            },
        }
        req = re.post("https://www.googleapis.com/youtube/v3/playlistItems?part=snippet", json=body, headers=headers)
        if not req.ok:
            print(req.text)
            session.pop("ytm_access_token")
            return redirect("/")

    data = {
        "link": "https://music.youtube.com/playlist?list=" + created_playlist_id
    }
    return render_template("ytmusic_playlist_created.html", data=data)


def spotify_create_playlist(playlist_name, playlist_description):
    user_id = session.get("user_id")
    endpoint = f"/users/{user_id}/playlists"
    body = {"name": playlist_name, "description": playlist_description}
    resp = spotify_hit_api(endpoint, method="POST", body=body)
    if not resp.ok or resp is None:
        print("error in creating spotify playlist")
        return None
    resp_body = resp.json()
    playlist_id = resp_body["id"]
    print("created playlist id - > ", playlist_id)

    return playlist_id


def spotify_add_songs_to_playlist(playlist_id, songs):
    endpoint = f"/playlists/{playlist_id}/tracks"
    body = {
        "uris": songs
    }
    resp = spotify_hit_api(endpoint, method="POST", body=body)
    if not resp.ok:
        return None
    return resp


def spotify_access_token(authorization_code):
    base_url = "https://accounts.spotify.com/api/token"
    joined_string = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    b64encoded_string = base64.b64encode(joined_string.encode()).decode()
    headers = {'content-type': 'application/x-www-form-urlencoded',
               "Authorization": "Basic " + b64encoded_string}
    body = {
        "code": authorization_code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    req = re.post(base_url, data=body, headers=headers)
    resp = req.json()
    return resp.get("access_token")


def ytm_access_token(authorization_code):
    base_url = "https://oauth2.googleapis.com/token"
    headers = {'content-type': 'application/x-www-form-urlencoded',
               }
    body = {
        "code": authorization_code,
        "redirect_uri": YTM_REDIRECT_URI,
        "grant_type": "authorization_code",
        "client_id": YTM_CLIENT_ID,
        "client_secret": YTM_CLIENT_SECRET
    }
    req = re.post(base_url, data=body, headers=headers)
    print(req.ok)
    print(req.text)
    resp = req.json()
    return resp.get("access_token")


def ytm_get_playlist_info(playlist_id):
    headers = {
        "Authorization": "Bearer " + session.get("ytm_access_token")
    }

    req1 = re.get(f"https://www.googleapis.com/youtube/v3/playlists?part=snippet&id={playlist_id}",
                  headers=headers)
    if not req1.ok:
        print("error in playlist-GET request")
        print(req1.text)
        return None, None, None

    resp = req1.json()
    title, description = resp["items"][0]["snippet"]["title"], resp["items"][0]["snippet"]["description"]

    req2 = re.get(f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={playlist_id}",
                  headers=headers)
    if not req2.ok:
        print("error in playlistItems-GET request")
        print(req2.text)
        return None, None, None

    resp = req2.json()
    tracks = resp["items"]
    total_results = resp["pageInfo"]["totalResults"]
    results_per_page = resp["pageInfo"]["resultsPerPage"]
    print("total results -> ", total_results)
    print("results per page -> ", results_per_page)
    if total_results > results_per_page:
        results_still_left = total_results - results_per_page
        print("results stil left ->", results_still_left)
        iterations = (results_still_left // results_per_page) + 1
        print("number of iteration -> ", iterations)
        next_page_token = resp["nextPageToken"]
        print("initial next page token -> ", next_page_token)
        for _ in range(iterations):
            req = re.get(
                f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={playlist_id}&pageToken={next_page_token}",
                headers=headers)
            if not req.ok:
                print("error in playlistItems-GET request")
                print(req.text)
                return None, None, None

            resp = req.json()
            tracks += resp["items"]
            next_page_token = resp.get("nextPageToken")
            print("changed next page token -> ", next_page_token)

    return title, description, tracks


def spotify_generate_redirect_string(client_id, scope, redirect_uri):
    baseURL = "https://accounts.spotify.com/authorize?"
    response_type = "code"
    client_id = client_id
    scope = scope
    redirect_uri = redirect_uri
    return f"{baseURL}&response_type={response_type}&client_id={client_id}&scope={scope}&redirect_uri={redirect_uri}"


def ytm_generate_redirect_string(client_id, scope, redirect_uri):
    baseURL = "https://accounts.google.com/o/oauth2/v2/auth?"
    response_type = "code"
    client_id = client_id
    scope = scope
    redirect_uri = redirect_uri
    return f"{baseURL}scope={scope}&included_granted_scopes=true&redirect_uri={redirect_uri}&response_type={response_type}&client_id={client_id}"


def spotify_authorized_user_id():
    endpoint = "/me"
    resp = spotify_hit_api(endpoint, method="GET")
    resp_body = resp.json()
    return resp_body["id"]


def spotify_hit_api(remainingURL, method="GET", body=None):
    baseURL = "https://api.spotify.com/v1"
    token = session.get("spotify_access_token")

    # print("************************")
    # print("Spotify Access Token -> " + token)
    # print("************************")

    if token is None:
        return None
    headers = {"Authorization": "Bearer " + token}

    # print("************************")
    # print(baseURL + remainingURL)
    # print("************************")
    resp = None
    if body is None:
        if method == "GET":
            print("did we come here ?")
            resp = re.get(baseURL + remainingURL, headers=headers)
        if method == "POST":
            resp = re.post(baseURL + remainingURL, headers=headers)

    else:
        if method == "GET":
            resp = re.get(baseURL + remainingURL, headers=headers, json=body)
        if method == "POST":
            print("we must have come here to create a playlist")
            resp = re.post(baseURL + remainingURL, headers=headers, json=body)

    if not resp.ok:
        print("--------------------")
        print(resp.json())
        print("--------------------")
        if resp.status_code == 401:
            session.pop("spotify_access_token")
            return None

    return resp


def spotify_search_song(title):
    endpoint = "/search?"
    type = "track"
    limit = 1
    URL = f"{endpoint}q={title}&type={type}&limit={limit}"
    resp = spotify_hit_api(URL, method="GET")
    if resp is None or not resp.ok:
        print("error in searching songs!!")
        return None

    resp_body = resp.json()
    song_id = resp_body["tracks"]["items"][0]["uri"]

    return song_id


def ytm_search_song(title):
    headers = {
        "Authorization": "Bearer " + session.get("ytm_access_token")
    }
    req = re.get(f"https://www.googleapis.com/youtube/v3/search?part=snippet&maxResults=3&q={title}", headers=headers)
    if not req.ok:
        print(req.text)
        return None
    resp = req.json()

    return resp["items"][0]["id"]["videoId"]


if __name__ == "__main__":
    app.run(debug=True)
