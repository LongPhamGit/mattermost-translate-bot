from flask import Flask, request, jsonify
from flask_socketio import SocketIO
import uuid

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route("/translate", methods=["POST"])
def translate():
    text = request.form.get("text", "")
    user = request.form.get("user_name", "")
    channel = request.form.get("channel_name", "")

    # Ví dụ: dịch đơn giản (thay thế thành code dịch thật)
    translated = f"[VI] {text}"

    message = {
        "id": str(uuid.uuid4()),
        "user": user,
        "channel": channel,
        "text": translated
    }

    # Phát sự kiện WebSocket
    socketio.emit("new_message", message)

    return jsonify({
        "status": "ok",
        "message": message
    })

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
