import hashlib
import json
import re
from datetime import datetime

import firebase_admin
import spotipy
from firebase_admin import credentials
from firebase_admin import firestore
from flask import Flask, request, render_template
from flask_httpauth import HTTPBasicAuth
from google.cloud.exceptions import Conflict
from spotipy.oauth2 import SpotifyClientCredentials

app = Flask(__name__)
auth = HTTPBasicAuth()

with open("spotipy-cred.json", "r") as _spotifyCredFile:
    spotipy_cred = json.load(_spotifyCredFile)
    client_id = spotipy_cred["client_id"]
    client_secret = spotipy_cred["client_secret"]

cred = credentials.Certificate('key.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

_users = db.collection("users")
_artists = db.collection("artists")

username_pattern = r"^[a-zA-Z0-9-]{1,32}$"


def md5hex(password):
    return hashlib.md5(password.encode()).hexdigest()


@app.route("/heartbeat", methods=['GET'])
def heartbeat():
    return "heartbeat returned at {}".format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


# https://flask-httpauth.readthedocs.io/en/latest/
@auth.verify_password
def verify_password(username, password):
    if bool(re.match(username_pattern, username)):
        if _users.document(username).get().exists:
            if _users.document(username).get().to_dict()["password"] == md5hex(password):
                return username


@app.route("/create-user", methods=['POST'])
def create_user():
    data = request.json
    user = data["user"]
    password = data["password"]  # todo: password validation
    password_hash = md5hex(password)

    if not bool(re.match(username_pattern, user)):
        return "username must be between 1-32 alphanumeric characters (a-z, A-Z, 0-9) and dashes (-)"

    try:
        _users.add(
            {
                "password": password_hash
            }, document_id=user
        )
        return "user {} created".format(user)
    except Conflict:
        return "user already exists"


@app.route("/rate-artist", methods=['GET', 'POST'])
@auth.login_required
def rate_artist():
    if request.method == 'GET':
        return render_template("rate-artist.html")

    rating = request.form
    user = auth.current_user()
    artist = rating["artist"]

    if artist is None or artist == "":
        return "artist field must not be blank"

    if not _users.document(user).get().exists:
        return "user {} does not exist".format(user)
    if not _artists.document(artist).get().exists:
        return "artist {} does not exist".format(artist)

    rating_ref = _users.document(user).collection("ratings").document(artist)
    rating_body = {
        "baddie": rating["baddie"],
        "banger": rating["banger"],
    }

    if rating_ref.get().exists:
        rating_ref.set(rating_body)
        # todo: update artist
        return "user {} rating successfully updated for artist {}".format(user, artist)
    else:
        rating_ref.create(rating_body)
        # todo: update artist
        return "user {} rating successfully recorded for artist {}".format(user, artist)


@app.route("/user-ratings/<user>", methods=['GET'])
def get_user_ratings(user):
    # todo: compile all ratings for a user into a single dictionary
    pass


@app.route("/add-artist", methods=['GET', 'POST'])
def add_artist():
    if request.method == 'GET':
        return render_template("add-artist.html")

    # todo: use spotify URI and use that to get the artist name
    # todo: include a 31x31 array in artist information to store all ratings
    data = request.form
    spotify = data["spotify"]

    try:
        client_credentials_manager = SpotifyClientCredentials(client_id, client_secret)
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
        artist_data = sp.artist(spotify)
        artist = artist_data["name"]
    except spotipy.client.SpotifyException as err:
        return "spotipy error: {}".format(err)

    try:
        _artists.add(
            {
                "num_ratings": 0,
                "sum_baddie": 0,
                "sum_banger": 0,
                "spotify": spotify,
            }, document_id=artist
        )
        return "artist {} created".format(artist)
    except Conflict:  # google.cloud.exceptions.Conflict
        return "artist {} already exists".format(artist)


@app.route("/", methods=['GET'])
@auth.login_required
def landing_page():
    return render_template("landing.html")


if __name__ == "__main__":
    app.run()
