import socketio

sio = socketio.Client()

@sio.on("connect")
def connect():
    print("✅ Connected to server")

@sio.on("new_message")
def on_new_message(data):
    print("📩 Tin nhắn mới:", data)

sio.connect("https://mattermost-translate-bot.onrender.com")
sio.wait()
