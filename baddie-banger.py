from flask import Flask
from datetime import datetime

app = Flask(__name__)


@app.route("/heartbeat", methods=['GET'])
def heartbeat(): 
    dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ret = "heartbeat returned at " + dt
    return ret


@app.route("/rate-artist", methods=['POST', 'PATCH'])
def rate_artist():
    return "rate artist"


@app.route("/my-ratings", methods=['GET'])
def get_my_ratings():
    return "get my ratings"


@app.route("/random-unrated-artist", methods=['GET'])
def get_random_unrated_artist():
    return "get random unrated artist"


@app.route("/artist-global-rating", methods=['GET'])
def get_artist_global_rating():
    return "get artist global rating"


@app.route("/all-global-ratings", methods=['GET'])
def get_all_global_ratings():
    return "get all global ratings"
