from flask import Flask, request, jsonify
from datetime import datetime
import json
import jsonschema
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from google import cloud
import hashlib

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


@app.route("/heartbeat", methods=['GET'])
def heartbeat():
    dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ret = "heartbeat returned at " + dt
    return ret


@app.route("/create-user", methods=['POST'])
def create_user():
    data = request.json
    user = data["user"]  # todo: username validation
    password = data["password"]
    password_hash = hashlib.md5(password.encode()).hexdigest()

    try:
        _users.add(
            {
                "password": password_hash
            },
            document_id=user
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
    pass


@app.route("/artist-ratings/<artist>", methods=['GET'])
def get_artist_global_rating(artist):
    pass


@app.route("/random-unrated-artist", methods=['GET'])
def get_random_unrated_artist():
    return "get random unrated artist"


@app.route("/all-global-ratings", methods=['GET'])
def get_all_global_ratings():
    return "get all global ratings"


@app.route("/admin-add-artist", methods=['POST'])
def admin_add_artist():
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
            },
            document_id=artist
        )
        return "artist {} created".format(artist)
    except cloud.exceptions.Conflict:
        return "artist already exists"


@app.route("/admin-update-artist", methods=['POST'])
def admin_update_artist():
    pass



if __name__ == "__main__":
    app.run()
