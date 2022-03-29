from flask import Flask
from datetime import datetime

app = Flask(__name__)


@app.route("/heartbeat/")
def heartbeat(): 
    dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ret = "heartbeat returned at " + dt
    return ret
