# Ở đầu file
import sys
import os
from datetime import datetime
import socketio
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit, QLabel
from PyQt6.QtCore import Qt
from plyer import notification

# Nếu Windows và muốn click notification:
try:
    from win10toast_click import ToastNotifier
    import threading
    use_win10toast = True
except ImportError:
    use_win10toast = False

SERVER_URL = "https://mattermost-translate-bot.onrender.com"
HTML_LOG = "translated_log.html"
META_REFRESH_SECONDS = 5

# (Các hàm init_html_file, escape_html, append_log_to_html giữ nguyên)

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
        self.text_log.setStyleSheet("font-size: 18pt;")  # Tăng cỡ chữ lên 2 size

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.text_log)
        self.setLayout(self.layout)

        self.sio = socketio.Client(reconnection=True, reconnection_attempts=5, reconnection_delay=2)
        self.sio.on("new_message", self.on_new_message)
        self.sio.on("connect", self.on_connect)
        self.sio.on("disconnect", self.on_disconnect)

        init_html_file()
        self.sio.connect(SERVER_URL)

        if use_win10toast:
            self.toaster = ToastNotifier()

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

        # Notification
        if use_win10toast:
            # Dùng win10toast-click để hỗ trợ click
            def on_click():
                self.show()
                self.raise_()
                self.activateWindow()

            threading.Thread(target=lambda: self.toaster.show_toast(
                f"Tin nhắn mới từ @{sender}",
                f"#{channel}: {translated}",
                duration=5,
                threaded=True,
                callback_on_click=on_click
            )).start()
        else:
            # Dùng plyer notification bình thường
            notification.notify(
                title=f"Tin nhắn mới từ @{sender}",
                message=f"#{channel}: {translated}",
                timeout=5
            )

        # Cập nhật số tin nhắn chưa đọc
        self.unread_count += 1
        self.label.setText(f"Số tin nhắn chưa đọc: {self.unread_count}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    demo = AppDemo()
    demo.show()
    sys.exit(app.exec())
