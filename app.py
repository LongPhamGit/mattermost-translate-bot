from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from deep_translator import GoogleTranslator
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

    try:
        # Dịch tự động sang tiếng Việt
        translated = GoogleTranslator(source="auto", target="vi").translate(text)
    except Exception as e:
        return jsonify({"error": f"Lỗi dịch: {e}"}), 500

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
