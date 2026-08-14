import os
import socket
import time

from flask import Flask, jsonify

app = Flask(__name__)
START = time.time()
VERSION = os.environ.get("APP_VERSION", "dev")


@app.route("/")
def index():
    return f"""<h1>hello-app</h1>
<p>host: {socket.gethostname()}</p>
<p>version: {VERSION}</p>
<p>uptime: {int(time.time() - START)}s</p>"""


@app.route("/health")
def health():
    return jsonify(status="ok", version=VERSION, host=socket.gethostname())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
