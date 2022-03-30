from flask import Flask, request
from datetime import datetime
import json
import jsonschema

app = Flask(__name__)

with open("persistence/schemas/rating-schema.json", "r") as _ratingSchemaFile:
    ratingSchema = json.load(_ratingSchemaFile)
    _ratingSchemaFile.close()
with open("persistence/schemas/artist-schema.json", "r") as _artistSchemaFile:
    artistSchema = json.load(_artistSchemaFile)
    _artistSchemaFile.close()

with open("persistence/ratings.json", "r") as _ratingsFile:
    ratings = json.load(_ratingsFile)
    _ratingsFile.close()
with open("persistence/artists.json", "r") as _artistsFile:
    artists = json.load(_artistsFile)
    _artistsFile.close()
with open("persistence/metadata.json", "r") as _metadataFile:
    metadata = json.load(_metadataFile)
    _metadataFile.close()


@app.route("/heartbeat", methods=['GET'])
def heartbeat():
    dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ret = "heartbeat returned at " + dt
    return ret


@app.route("/rate-artist", methods=['POST', 'PATCH'])
def rate_artist():
    # todo: populate timestamp and rating id yourself
    rating = request.json
    try:
        rating_id = metadata["current_rating"]
        rating["id"] = rating_id
        rating["timestamp"] = datetime.now().isoformat()
        jsonschema.validate(instance=rating, schema=ratingSchema)

        metadata["current_rating"] = rating_id + 1
        with open("persistence/metadata.json", "w") as metadataFile:
            json.dump(metadata, metadataFile)
            metadataFile.close()

        ratings.append(rating)
        with open("persistence/ratings.json", "w") as ratingsFile:
            json.dump(ratings, ratingsFile)
            ratingsFile.close()

        return "rating successfully recorded"
    except jsonschema.exceptions.ValidationError as err:
        print(err)
        return "rating has following error: {}".format(str(err))


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


@app.route("/admin-add-artist", methods=['POST'])
def admin_add_artist():
    pass


@app.route("/admin-update-artist", methods=['POST'])
def admin_update_artist():
    pass


@app.route("/admin-dev-reset", methods=['POST'])
def admin_dev_reset():
    metadata["current_rating"] = 0
    with open("persistence/metadata.json", "w") as metadataFile:
        json.dump(metadata, metadataFile)
        metadataFile.close()

    with open("persistence/ratings.json", "w") as ratingsFile:
        json.dump([], ratingsFile)
        ratingsFile.close()

    with open("persistence/artists.json", "w") as artistsFile:
        json.dump([], artistsFile)
        artistsFile.close()

    return "all databases reset"


if __name__ == "__main__":
    app.run()
