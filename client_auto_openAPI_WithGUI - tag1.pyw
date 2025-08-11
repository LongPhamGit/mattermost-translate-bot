# gemini_translate_app.pyw
import sys
import os
import threading
import json
import requests
from datetime import datetime
import socketio
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit, QLabel
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor
from PyQt6.QtCore import Qt

# Thay bằng API key Gemini của bạn
API_KEY = "AIzaSyBMFbvl0poru2Xs1mUZfhrlhuYisItGiqQ"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Socket.IO server URL
SERVER_URL = "https://mattermost-translate-bot.onrender.com"

# Hàm gọi Gemini API để dịch
def call_gemini_translate(text, target_language="vi"):
    prompt_text = f"Dịch sang tiếng {target_language}, giữ nguyên ý nghĩa: {text}"
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": API_KEY,
    }
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text}
                ]
            }
        ]
    }

    try:
        response = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f"[Lỗi dịch Gemini]: {e}"

def escape_html(s):
    if s is None:
        return ""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&#39;"))

def append_log_to_html(original, translated, sender, channel):
    HTML_LOG = "translated_log.html"
    META_REFRESH_SECONDS = 5
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

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html_snip = f"""
<div class="entry">
<div class="timestamp">🕒 {timestamp}</div>
<b>👤 @{sender}</b> tại <code>#{channel}</code>
<div class="original">💬 <b>Gốc:</b> {escape_html(original)}</div>
<div class="translated">🔁 <b>Dịch:</b> {escape_html(translated)}</div>
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

class GeminiTranslateApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📨 Tổng số tin nhắn (Dịch bằng Gemini)")
        self.resize(650, 450)
        self.setStyleSheet("background-color: #f0f2f5;")

        self.total_count = 0

        self.layout = QVBoxLayout()
        self.label = QLabel("📨 Tổng số tin nhắn: 0")
        self.label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.label.setStyleSheet("color: #333333;")
        self.layout.addWidget(self.label)

        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setFont(QFont("Consolas", 12))
        self.text_log.setStyleSheet("background-color: white; border: 1px solid #ccc; padding: 8px;")
        self.layout.addWidget(self.text_log)

        self.setLayout(self.layout)

        self.sio = socketio.Client(reconnection=True, reconnection_attempts=5, reconnection_delay=2)
        self.sio.on("new_message", self.on_new_message)
        self.sio.on("connect", self.on_connect)
        self.sio.on("disconnect", self.on_disconnect)

        # Khởi tạo file log HTML
        append_log_to_html("", "", "", "")  # tạo file nếu chưa có

        threading.Thread(target=self.sio.connect, args=(SERVER_URL,), daemon=True).start()

    def on_connect(self):
        self.append_log_text("✅ Đã kết nối tới server.\n")

    def on_disconnect(self):
        self.append_log_text("❌ Mất kết nối tới server.\n")

    def append_log_text(self, text, color="#000000"):
        cursor = self.text_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(text, fmt)
        self.text_log.setTextCursor(cursor)
        self.text_log.ensureCursorVisible()

    def on_new_message(self, data):
        sender = data.get("user", "unknown")
        channel = data.get("channel", "unknown")
        original = data.get("original", "")
        #self.append_log_text(f"🕒 Đang dịch tin nhắn mới từ @{sender}...\n", "#0078D7")

        # Dịch Gemini trong thread tránh block UI
        def do_translate():
            translated = call_gemini_translate(original, "vi")
            log_text = f"📩 Từ @{sender} trong #{channel}\n💬 {original}\n🔁 {translated}\n---------------------------\n\n"
            self.append_log_text(log_text, "#000000")
            append_log_to_html(original, translated, sender, channel)
            self.total_count += 1
            self.label.setText(f"📨 Tổng số tin nhắn: {self.total_count}")

        threading.Thread(target=do_translate, daemon=True).start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeminiTranslateApp()
    window.show()
    sys.exit(app.exec())
