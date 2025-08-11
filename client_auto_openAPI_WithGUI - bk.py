import sys
import os
from datetime import datetime
import socketio
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit, QLabel
from PyQt6.QtCore import Qt
from plyer import notification

SERVER_URL = "https://mattermost-translate-bot.onrender.com"
HTML_LOG = "translated_log.html"
META_REFRESH_SECONDS = 5

# Tạo file HTML nếu chưa có
def init_html_file():
    if not os.path.exists(HTML_LOG):
        with open(HTML_LOG, "w", encoding="utf-8") as f:
            f.write(f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Translated Logs</title>
<meta http-equiv="refresh" content="{META_REFRESH_SECONDS}">
<style>
body {{ font-family: sans-serif; background:#f5f5f5; padding:20px; }}
.entry {{ background:white; padding:10px; margin-bottom:10px; border-left:5px solid #4caf50; }}
.timestamp {{ font-size:12px; color:#999; }}
.original {{ margin-top:8px; }}
.translated {{ color:green; margin-top:6px; }}
</style>
</head>
<body>
<h2>📘 Lịch sử bản dịch</h2>
<!-- entries appended below -->
</body>
</html>
""")

def escape_html(s):
    if s is None:
        return ""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&#39;"))

def append_log_to_html(original, translated, sender, channel):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html_snip = f"""
<div class="entry">
<div class="timestamp">🕒 {timestamp}</div>
<b>👤 @{sender}</b> tại <code>#{channel}</code>
<div class="original">💬 <b>Gốc:</b> {escape_html(original)}</div>
<div class="translated">🈶 <b>Dịch:</b> {escape_html(translated)}</div>
</div>
"""
    with open(HTML_LOG, "r", encoding="utf-8") as f:
        content = f.read()
    idx = content.rfind("</body>")
    if idx == -1:
        new = content + html_snip
    else:
        new = content[:idx] + html_snip + content[idx:]
    with open(HTML_LOG, "w", encoding="utf-8") as f:
        f.write(new)

# GUI app
class AppDemo(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SocketIO Message Logger")
        self.resize(600, 400)

        self.unread_count = 0

        self.layout = QVBoxLayout()
        self.label = QLabel("Số tin nhắn chưa đọc: 0")
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.text_log)
        self.setLayout(self.layout)

        self.sio = socketio.Client(reconnection=True, reconnection_attempts=5, reconnection_delay=2)
        self.sio.on("new_message", self.on_new_message)
        self.sio.on("connect", self.on_connect)
        self.sio.on("disconnect", self.on_disconnect)

        init_html_file()
        self.sio.connect(SERVER_URL)

    def on_connect(self):
        self.text_log.append("✅ Connected to server.")

    def on_disconnect(self):
        self.text_log.append("❌ Disconnected from server.")

    def on_new_message(self, data):
        sender = data.get("user")
        channel = data.get("channel")
        original = data.get("original")
        translated = data.get("translated")

        log_text = f"📩 New message from @{sender} in #{channel}\nGốc: {original}\nDịch: {translated}\n"
        self.text_log.append(log_text)

        append_log_to_html(original, translated, sender, channel)

        # Notification desktop
        notification.notify(
            title=f"Tin nhắn mới từ @{sender}",
            message=f"#{channel}: {translated}",
            timeout=5
        )

        # Update số tin nhắn chưa đọc
        self.unread_count += 1
        self.label.setText(f"Số tin nhắn chưa đọc: {self.unread_count}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    demo = AppDemo()
    demo.show()
    sys.exit(app.exec())
