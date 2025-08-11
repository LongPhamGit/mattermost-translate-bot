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

try:
    from win10toast_click import ToastNotifier
    use_win10toast = True
except ImportError:
    use_win10toast = False
    from plyer import notification


# Load config
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

API_KEY = config["API_KEY"]
GEMINI_URL = config["GEMINI_URL"]
SERVER_URL = config["SERVER_URL"]
MAX_LOG_ENTRIES = config["MAX_LOG_ENTRIES"]
HTML_LOG = config["HTML_LOG"]
META_REFRESH_SECONDS = config["META_REFRESH_SECONDS"]


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
    # Tạo file nếu chưa có
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

    # Đọc nội dung cũ, lấy danh sách entries hiện tại
    with open(HTML_LOG, "r", encoding="utf-8") as f:
        content = f.read()

    # Tách phần giữa <body> và </body> để xử lý log entries
    body_start = content.find("<body>")
    body_end = content.rfind("</body>")

    if body_start == -1 or body_end == -1 or body_end <= body_start:
        # Trường hợp file bị hỏng hoặc không đúng định dạng, ghi lại mới
        entries = []
    else:
        body_content = content[body_start+6:body_end]
        # Tách các entry qua div.entry
        entries = []
        split_entries = body_content.split('<div class="entry">')
        for part in split_entries[1:]:
            entries.append('<div class="entry">' + part)

    # Thêm entry mới vào đầu (hoặc cuối tùy bạn)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = f"""
<div class="entry">
<div class="timestamp">🕒 {timestamp}</div>
<b>👤 @{escape_html(sender)}</b> tại <code>#{escape_html(channel)}</code>
<div class="original">💬 <b>Gốc:</b> {escape_html(original)}</div>
<div class="translated">🔁 <b>Dịch:</b> {escape_html(translated)}</div>
</div>
"""
    entries.append(new_entry)

    # Giới hạn số entries tối đa
    if len(entries) > MAX_LOG_ENTRIES:
        entries = entries[-MAX_LOG_ENTRIES:]  # giữ 200 entry cuối cùng

    # Tạo lại body mới
    new_body = "\n".join(entries)

    # Tạo lại toàn bộ file
    new_content = content[:body_start+6] + new_body + content[body_end:]

    with open(HTML_LOG, "w", encoding="utf-8") as f:
        f.write(new_content)

class GeminiTranslateApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📨 Kiểm tra tin nhắn (kèm bản dịch bằng Gemini)")
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

        # Khởi tạo file log HTML nếu chưa có
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

        threading.Thread(target=self.sio.connect, args=(SERVER_URL,), daemon=True).start()

        if use_win10toast:
            self.toaster = ToastNotifier()

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

        def do_translate():
            translated = call_gemini_translate(original, "vi")
            log_text = f"📩 Từ @{sender} trong #{channel}\n💬 {original}\n🔁 {translated}\n---------------------------\n\n"
            self.append_log_text(log_text, "#000000")
            append_log_to_html(original, translated, sender, channel)
            self.total_count += 1
            self.label.setText(f"📨 Tổng số tin nhắn: {self.total_count}")

            # Hiển thị thông báo desktop
            title = f"Tin nhắn mới từ @{sender}"
            message = f"#{channel}: {translated}"

            def on_notification_click():
                self.show()
                self.raise_()
                self.activateWindow()

            if use_win10toast:
                threading.Thread(target=lambda: self.toaster.show_toast(
                    title,
                    message,
                    duration=5,
                    threaded=True,
                    callback_on_click=on_notification_click
                )).start()
            else:
                notification.notify(
                    title=title,
                    message=message,
                    timeout=5
                )
                # plyer không hỗ trợ click callback

        threading.Thread(target=do_translate, daemon=True).start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeminiTranslateApp()
    window.show()
    sys.exit(app.exec())
