from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import json
import os
import uuid

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app, cors_allowed_origins="*")

TOKENS_FILE = "tokens.json"
LOG_FILE = "translated_log.json"
REG_CODE = os.environ.get("REG_CODE", "myregcode123")  # mã đăng ký extension
API_TOKEN = os.environ.get("API_TOKEN", None)  # legacy token

# Load tokens
if os.path.exists(TOKENS_FILE):
    with open(TOKENS_FILE, "r") as f:
        TOKENS = json.load(f)
else:
    TOKENS = {}

# Load logs
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r") as f:
        MESSAGES = json.load(f)
else:
    MESSAGES = []

def save_tokens():
    with open(TOKENS_FILE, "w") as f:
        json.dump(TOKENS, f)

def save_messages():
    with open(LOG_FILE, "w") as f:
        json.dump(MESSAGES, f)

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    reg_code = data.get("reg_code")
    if reg_code != REG_CODE:
        return jsonify({"error": "Invalid registration code"}), 403
    token = str(uuid.uuid4())
    TOKENS[token] = {"created": True}
    save_tokens()
    return jsonify({"token": token})

@app.route("/translate", methods=["POST"])
def translate():
    token = request.headers.get("Authorization")
    if API_TOKEN and token != f"Bearer {API_TOKEN}":
        return jsonify({"error": "Unauthorized"}), 401

    text = request.form.get("text", "")
    user_name = request.form.get("user_name", "")
    channel_name = request.form.get("channel_name", "")

    message = {
        "id": str(uuid.uuid4()),
        "user": user_name,
        "channel": channel_name,
        "text": text,
    }
    MESSAGES.append(message)
    save_messages()

    socketio.emit("new_message", message)
    return jsonify({"status": "ok", "message": message})

@app.route("/logs")
def logs():
    return jsonify(MESSAGES)

@app.route("/log_page")
def log_page():
    return send_from_directory(".", "translated_log.html")

@socketio.on("connect")
def handle_connect():
    print("Client connected")

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
