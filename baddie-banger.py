import hashlib
import json
import re
from datetime import datetime
import time
import os
from urllib.request import urlopen

import requests

import firebase_admin
import spotipy
from firebase_admin import credentials
from firebase_admin import firestore
from flask import Flask, request, render_template, redirect, url_for, session
from google.cloud.exceptions import Conflict
from spotipy.oauth2 import SpotifyClientCredentials
from PIL import Image

app = Flask(__name__)

with open("security.json", "r") as _securityCredFile:
    security = json.load(_securityCredFile)
    client_id = security["spotify_client_id"]
    client_secret = security["spotify_client_secret"]
    app.config["SECRET_KEY"] = security["secret_key"]

cred = credentials.Certificate('security.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

_users = db.collection("users")
_artists = db.collection("artists")
_artist_list = db.collection("metadata").document("artist_list")

all_artist_map = {
    doc.id: doc.get().to_dict()["spotify"] for doc in _artists.list_documents()
}
all_artist_list = list(all_artist_map.keys())
_artist_list.set({"artist_list": all_artist_map})

username_pattern = r"^[a-zA-Z0-9-]{1,32}$"
session_user_key = "user"
session_last_interacted_key = "last_interacted"


@app.before_request
def refresh_session():
    if session_last_interacted_key in session.keys() and session[session_last_interacted_key] is not None:
        last = int(session[session_last_interacted_key])
        current = int(time.time())
        delta = (current - last)
        print(datetime.utcfromtimestamp(last))
        if delta > 600:  # ten mins of inactivity -> logout
            session[session_user_key] = None
            session[session_last_interacted_key] = None
        else:
            session[session_last_interacted_key] = str(current)


def md5hex(password):
    return hashlib.md5(password.encode()).hexdigest()


def verify_password(username, password):
    if bool(re.match(username_pattern, username)):
        user_doc = _users.document(username).get()
        if user_doc.exists and user_doc.to_dict()["password"] == md5hex(password):
            return username
    return None


@app.route("/heartbeat", methods=['GET'])
def heartbeat():
    return "heartbeat returned at {}".format(datetime.now().isoformat())


@app.route("/create-user", methods=['GET', 'POST'])
def create_user():
    if request.method == 'GET':
        return render_template("create-user.html")

    data = request.form
    user = data["username"]
    password = data["password"]  # todo: password validation
    password_hash = md5hex(password)

    if not bool(re.match(username_pattern, user)):
        message = "username must be between 1-32 alphanumeric characters (a-z, A-Z, 0-9) and dashes (-)"
        return render_template("homepage.html", message=message)

    try:
        _users.add(
            {
                "password": password_hash,
                "ratings": dict()
            }, document_id=user
        )
        message = "user {} created".format(user)
    except Conflict:
        message = "user already exists"

    return login_logic(user, password)


@app.route("/logout", methods=['GET'])
def logout():
    session[session_user_key] = None
    session[session_last_interacted_key] = None
    return redirect(url_for("login"))


@app.route("/rate-artist", methods=['GET', 'POST'])
def rate_artist():
    if session_user_key not in session.keys() or session[session_user_key] is None:
        return render_template("homepage.html", message="must login to continue")

    user = session[session_user_key]

    if request.method == 'GET':
        artist_list = sorted(all_artist_list + [""])
        return render_template("rate-artist.html", user=user, artist_list=artist_list)

    rating = request.form
    artist = rating["artist"]
    baddie = int(rating["baddie"])
    banger = int(rating["banger"])

    if artist is None or artist == "":
        return render_template("homepage.html", message="artist field must not be blank")

    user_ref = _users.document(user)
    artist_ref = _artists.document(artist)

    if not user_ref.get().exists:
        return render_template("homepage.html", message="user {} does not exist".format(user))
    if not artist_ref.get().exists:
        return render_template("homepage.html", message="artist {} does not exist".format(artist))

    user_body = user_ref.get().to_dict()
    artist_body = artist_ref.get().to_dict()

    if artist in user_body["ratings"]:
        prev_baddie = user_body["ratings"][artist]["baddie"]
        prev_banger = user_body["ratings"][artist]["banger"]
        artist_body["sum_baddie"] += (baddie - prev_baddie)
        artist_body["sum_banger"] += (banger - prev_banger)
        key = str((baddie, banger))
        prev_key = str((prev_baddie, prev_banger))
        artist_body["ratings_data"][prev_key] -= 1
        if key in artist_body["ratings_data"]:
            artist_body["ratings_data"][key] += 1
        else:
            artist_body["ratings_data"][key] = 1
        artist_ref.set(artist_body)
        message = "user {} rating successfully updated for artist {}".format(user, artist)
    else:
        artist_body["num_ratings"] += 1
        artist_body["sum_baddie"] += baddie
        artist_body["sum_banger"] += banger
        key = str((baddie, banger))
        if key in artist_body["ratings_data"]:
            artist_body["ratings_data"][key] += 1
        else:
            artist_body["ratings_data"][key] = 1
        artist_ref.set(artist_body)
        message = "user {} rating successfully recorded for artist {}".format(user, artist)

    user_body["ratings"][artist] = {
        "baddie": baddie,
        "banger": banger,
    }
    user_ref.set(user_body)
    return render_template("homepage.html", message=message)


# https://stackoverflow.com/questions/22566284/matplotlib-how-to-plot-images-instead-of-points
@app.route("/user-ratings/<user>", methods=['GET'])
def get_user_ratings(user):
    user_ref = _users.document(user)
    if not user_ref.get().exists:
        return render_template("homepage.html", message="user {} does not exist".format(user))

    client_credentials_manager = SpotifyClientCredentials(client_id, client_secret)
    sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

    raw_ratings = user_ref.get().to_dict()["ratings"]
    artists = raw_ratings.keys()
    ratings = list()
    for artist in artists:
        ratings.append({
            "name": artist,
            "baddie": raw_ratings[artist]["baddie"],
            "banger": raw_ratings[artist]["banger"],
            "img": get_artist_image(sp, artist)
        })
    return render_template("user-ratings.html", user=user, ratings=ratings)
    # todo: make pretty

    pass


@app.route("/add-artist", methods=['GET', 'POST'])
def add_artist():
    if request.method == 'GET':
        return render_template("add-artist.html")

    spotify = None
    try:
        spotify = request.form["spotify"]
    except KeyError:
        spotify = request.json["spotify"]
    finally:
        if spotify is None:
            message = "invalid POST data (no form or json)"
            return render_template("homepage.html", message=message)
    try:
        client_credentials_manager = SpotifyClientCredentials(client_id, client_secret)
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
        artist_data = sp.artist(spotify)
        artist = artist_data["name"]
    except spotipy.client.SpotifyException as err:
        message = "spotipy error: {}".format(err)
        return render_template("homepage.html", message=message)

    if artist not in all_artist_map:
        _artists.add(
            {
                "num_ratings": 0,
                "sum_baddie": 0,
                "sum_banger": 0,
                "spotify": spotify,
                "ratings_data": dict(),
            }, document_id=artist
        )
        all_artist_map[artist] = spotify
        all_artist_list.append(artist)
        _artist_list.set({"artist_list": all_artist_map})
        message = "artist {} created".format(artist)
    else:
        message = "artist {} already exists".format(artist)
    return render_template("homepage.html", message=message)


@app.route("/", methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template("login.html")
    else:
        login_info = request.form
        return login_logic(login_info["username"], login_info["password"])


def login_logic(username, password):
    username = verify_password(username, password)
    if username is not None:
        session[session_user_key] = username
        session[session_last_interacted_key] = int(time.time())
        print(session)
        return redirect(url_for("rate_artist"))
    else:
        message = "User could not be authenticated"
        return render_template("homepage.html", message=message)


def get_artist_image(sp, artist):
    filepath = "images/{}.jpg".format(artist.replace(" ", "_"))
    if not os.path.exists("static/{}".format(filepath)):
        artist = sp.artist(all_artist_map[artist])
        artist_img = artist["images"][0]["url"]
        img = Image.open(urlopen(artist_img))
        img.save(filepath)
    return filepath


if __name__ == "__main__":
    app.run()
