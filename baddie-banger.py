import hashlib
import json
import re
from datetime import datetime

import firebase_admin
import jsonschema
from firebase_admin import credentials
from firebase_admin import firestore
from flask import Flask, request
from google import cloud

app = Flask(__name__)

with open("schemas/rating-schema.json", "r") as _ratingSchemaFile:
    ratingSchema = json.load(_ratingSchemaFile)
    _ratingSchemaFile.close()
with open("schemas/artist-schema.json", "r") as _artistSchemaFile:
    artistSchema = json.load(_artistSchemaFile)
    _artistSchemaFile.close()

cred = credentials.Certificate('key.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

_users = db.collection("users")
_artists = db.collection("artists")

username_pattern = r"^[a-zA-Z0-9-]{1,32}$"


@app.route("/heartbeat", methods=['GET'])
def heartbeat():
    return "heartbeat returned at {}".format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


@app.route("/create-user", methods=['POST'])
def create_user():
    data = request.json
    user = data["user"]
    password = data["password"] # todo: password validation
    password_hash = hashlib.md5(password.encode()).hexdigest()

    if not bool(re.match(username_pattern, user)):
        return "username must be between 1-32 alphanumeric characters (a-z, A-Z, 0-9) and dashes (-)"

    try:
        _users.add(
            {
                "password": password_hash
            }, document_id=user
        )
        return "user {} created".format(user)
    except cloud.exceptions.Conflict:
        return "user already exists"


@app.route("/rate-artist", methods=['POST'])
def rate_artist():
    rating = request.json
    try:
        jsonschema.validate(instance=rating, schema=ratingSchema)
    except jsonschema.exceptions.ValidationError as err:
        return "rating has following error: {}".format(str(err))

    user = rating["user"]
    artist = rating["artist"]

    if not _users.document(user).get().exists:
        return "user does not exist"
    if not _artists.document(artist).get().exists:
        return "artist does not exist"

    rating_ref = _users.document(user).collection("ratings").document(artist)
    rating_body = {
                "baddie": rating["baddie"],
                "banger": rating["banger"],
            }

    if rating_ref.get().exists:
        rating_ref.set(rating_body)
        # todo: update artist
        return "rating successfully updated"
    else:
        rating_ref.create(rating_body)
        # todo: update artist
        return "rating successfully recorded"


@app.route("/user-ratings/<user>", methods=['GET'])
def get_user_ratings(user):
    # todo: compile all ratings for a user into a single dictionary
    pass


@app.route("/admin-add-artist", methods=['POST'])
def admin_add_artist():
    # todo: use spotify URI and use that to get the artist name
    # todo: include a 31x31 array in artist information to store all ratings
    data = request.json
    artist = data["artist"]  # todo: artist name validation
    spotify = data["spotify"]

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
    except cloud.exceptions.Conflict:
        return "artist already exists"


if __name__ == "__main__":
    app.run()
