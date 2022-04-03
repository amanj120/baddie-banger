import hashlib
import json
import re
from datetime import datetime, timedelta

import firebase_admin
import spotipy
from firebase_admin import credentials
from firebase_admin import firestore
from flask import Flask, request, render_template, redirect, url_for, session
from google.cloud.exceptions import Conflict
from spotipy.oauth2 import SpotifyClientCredentials

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

username_pattern = r"^[a-zA-Z0-9-]{1,32}$"
session_user_key = "user"
session_last_interacted_key = "last_interacted"


@app.before_request
def refresh_session():
    if session_last_interacted_key in session.keys() and session[session_last_interacted_key] is not None:
        last = datetime.fromisoformat(str(session[session_last_interacted_key]))
        current = datetime.utcnow()
        delta = (current - last).total_seconds()
        print(last.isoformat())
        if delta > 3600: # one hour
            session[session_user_key] = None
            session[session_last_interacted_key] = None
            return redirect(url_for(login))
        else:
            session[session_last_interacted_key] = str(current)
    else:
        return redirect(url_for(login))


def md5hex(password):
    return hashlib.md5(password.encode()).hexdigest()


def verify_password(username, password):
    if bool(re.match(username_pattern, username)):
        if _users.document(username).get().exists:
            if _users.document(username).get().to_dict()["password"] == md5hex(password):
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
        return "username must be between 1-32 alphanumeric characters (a-z, A-Z, 0-9) and dashes (-)"

    try:
        _users.add(
            {"password": password_hash}, document_id=user
        )
        return "user {} created".format(user)
    except Conflict:
        return "user already exists"


@app.route("/logout", methods=['GET'])
def logout():
    session[session_user_key] = None
    session[session_last_interacted_key] = None
    return redirect(url_for("login"))


@app.route("/rate-artist", methods=['GET', 'POST'])
def rate_artist():
    if session_user_key in session.keys():
        if session[session_user_key] is None:
            return "must login to continue"

    user = session[session_user_key]

    if request.method == 'GET':
        return render_template("rate-artist.html", user=user)

    rating = request.form
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


@app.route("/", methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template("login.html")
    else:
        login_info = request.form
        username = verify_password(login_info["username"], login_info["password"])
        if username is not None:
            session[session_user_key] = username
            # todo: session expiration
            session[session_last_interacted_key] = str(datetime.utcnow().isoformat())
            print(session)
            return redirect(url_for("rate_artist"))
        else:
            return "User could not be authenticated"


if __name__ == "__main__":
    app.run()
