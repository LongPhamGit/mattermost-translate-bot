from flask import Flask, request, jsonify
from flask_socketio import SocketIO
import uuid
import os

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

@app.route("/")
def home():
    return "✅ Mattermost Translate Bot WebSocket Server is running"

@app.route("/translate", methods=["POST"])
def translate():
    text = request.form.get("text", "")
    user = request.form.get("user_name", "")
    channel = request.form.get("channel_name", "")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    # Thay bằng code dịch thật (GoogleTranslator...) nếu muốn
    translated = f"[VI] {text}"

    message = {
        "id": str(uuid.uuid4()),
        "user": user,
        "channel": channel,
        "original": text,
        "translated": translated
    }

    # Gửi tin nhắn mới tới tất cả client WebSocket
    socketio.emit("new_message", message)

    return jsonify({
        "status": "ok",
        "message": message
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
