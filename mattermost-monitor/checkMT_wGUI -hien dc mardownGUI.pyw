# mattermost_qt_webview.py
import sys
import os
import json
import html as html_lib
import threading
from datetime import datetime

import requests
import websocket
from markdown import markdown

from PyQt6.QtCore import pyqtSignal, QObject, QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QMessageBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView

# Optional notifications
import platform
USE_WIN_CLICK = (platform.system() == "Windows")
TOASTER = None
if USE_WIN_CLICK:
    try:
        from win10toast_click import ToastNotifier
        TOASTER = ToastNotifier()
    except Exception:
        TOASTER = None

try:
    from plyer import notification as plyer_notification
except Exception:
    plyer_notification = None

# ---------------- Config load (unchanged behavior) ----------------
CONFIG_FILE = "config.json"
if not os.path.exists(CONFIG_FILE):
    raise SystemExit(f"Missing {CONFIG_FILE} in current folder.")

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

SERVER_URL      = config.get("SERVER_URL", "http://localhost:8065")
WS_URL          = config.get("WS_URL", "ws://localhost:8065/api/v4/websocket")
MMUSERID        = config.get("MMUSERID", "")
MMAUTHTOKEN     = config.get("MMAUTHTOKEN", "")
MY_USERNAME     = config.get("MY_USERNAME", "lpham")
WATCH_CHANNELS  = config.get("WATCH_CHANNELS", [])
CHANNEL_MAP     = config.get("_comment", {})   # channel_id -> name
USER_MAP        = config.get("USER_MAP", {})   # user_id -> username
API_KEY         = config.get("API_KEY", "")
GEMINI_URL      = config.get("GEMINI_URL", "")
HTML_LOG_FILE   = config.get("HTML_LOG", "messages.html")

cookies = {"MMUSERID": MMUSERID, "MMAUTHTOKEN": MMAUTHTOKEN}

# ---------------- HTML header/footer & rotation ----------------
MAX_LOG_BYTES = 5 * 1024 * 1024
ROTATE_TARGET_RATIO = 0.9

HTML_HEADER = """<html><head><meta charset='utf-8'>
<style>
body {font-family: Arial, sans-serif; font-size:14px; background:#f4f6f8; margin:20px;}
.container {max-width:1000px; margin:0 auto;}
.msg {margin:12px 0; padding:12px 14px; border:1px solid #e0e0e0;
      border-radius:8px; background:#fff; box-shadow:0 1px 2px rgba(0,0,0,0.05);}
.msg:nth-child(even){background:#fbfbfb;}
.timestamp {color:#666; font-size:12px; margin-bottom:6px;}
.sender {font-weight:600; color:#0b8043;}
.channel {color:#3367d6; font-style:italic;}
.content {margin-top:6px; color:#111; line-height:1.4; white-space:normal; word-wrap:break-word;}
.mention .content { color:#b00020; font-weight:700; }
.translated {margin-top:8px; padding-left:12px; border-left:3px solid #eee;
            font-style:italic; color:#555; white-space:normal; word-wrap:break-word;}
</style></head><body><div class="container">\n"""

HTML_FOOTER = "</div></body></html>\n"

def init_html_log():
    if not os.path.exists(HTML_LOG_FILE):
        with open(HTML_LOG_FILE, "w", encoding="utf-8") as f:
            f.write(HTML_HEADER + HTML_FOOTER)

def rotate_html_log_if_needed():
    try:
        if not os.path.exists(HTML_LOG_FILE):
            return
        size = os.path.getsize(HTML_LOG_FILE)
        if size <= MAX_LOG_BYTES:
            return
        with open(HTML_LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        # separate header & body
        if HTML_HEADER in content:
            body = content.replace(HTML_HEADER, "").replace(HTML_FOOTER, "")
            # split blocks
            parts = body.split("<div class='msg")
            if len(parts) <= 1:
                return
            prefix = parts[0]
            blocks = ["<div class='msg" + p for p in parts[1:]]
            target_size = int(MAX_LOG_BYTES * ROTATE_TARGET_RATIO)
            kept = []
            for i in range(len(blocks)-1, -1, -1):
                kept.append(blocks[i])
                candidate = HTML_HEADER + prefix + "".join(reversed(kept)) + HTML_FOOTER
                if len(candidate.encode("utf-8")) >= target_size:
                    break
            with open(HTML_LOG_FILE, "w", encoding="utf-8") as f:
                f.write(HTML_HEADER + prefix + "".join(reversed(kept)) + HTML_FOOTER)
    except Exception:
        pass

def append_html(sender, channel_name, text, css_class="normal", translated=""):
    rotate_html_log_if_needed()
    # escape -> convert markdown to HTML so GUI and file log match
    safe_text = html_lib.escape(text or "")
    safe_trans = html_lib.escape(translated or "")
    html_text = markdown(safe_text, extensions=["fenced_code", "tables"])
    html_trans = markdown(safe_trans, extensions=["fenced_code", "tables"]) if safe_trans else ""
    content_cls = "mention" if css_class == "mention" else ""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"<div class='msg {content_cls}'>"
        f"<div class='timestamp'>[{html_lib.escape(ts)}]</div>"
        f"<div><span class='sender'>{html_lib.escape(sender)}</span> "
        f"in <span class='channel'>{html_lib.escape(channel_name)}</span></div>"
        f"<div class='content'>{html_text}</div>"
    )
    if html_trans:
        entry += f"<div class='translated'>{html_trans}</div>"
    entry += "</div>\n"
    # insert before footer
    try:
        if os.path.exists(HTML_LOG_FILE):
            with open(HTML_LOG_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            if content.endswith(HTML_FOOTER):
                new_content = content[:-len(HTML_FOOTER)] + entry + HTML_FOOTER
            else:
                new_content = content + entry
            with open(HTML_LOG_FILE, "w", encoding="utf-8") as f:
                f.write(new_content)
        else:
            with open(HTML_LOG_FILE, "w", encoding="utf-8") as f:
                f.write(HTML_HEADER + entry + HTML_FOOTER)
    except Exception:
        try:
            with open(HTML_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass

init_html_log()

# ---------------- Gemini translate (same pattern) ----------------
def call_gemini_translate(text: str, target_language: str = "vi") -> str:
    if not API_KEY or not GEMINI_URL:
        return ""  # if not configured, return empty to skip translate
    prompt_text = f"Dịch sang tiếng {target_language}, giữ nguyên ý nghĩa: {text}"
    headers = {"Content-Type": "application/json", "X-goog-api-key": API_KEY}
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}
    try:
        resp = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return "🔁 " + data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return "[Lỗi dịch]"

# ---------------- PyQt Signals container ----------------
class Signals(QObject):
    new_message = pyqtSignal(str, str, str, str)  # sender, channel, message, translated (css_class inside message?)
    set_connected = pyqtSignal(bool)
    update_count = pyqtSignal(int)

signals = Signals()

# ---------------- Main GUI (keeps your original layout controls) ----------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mattermost Monitor – WebEngine")
        self.resize(980, 760)

        # top row: Open log, Clear, message counter, status label (kept)
        top_layout = QHBoxLayout()
        self.btn_open = QPushButton("Mở file log HTML")
        self.btn_clear = QPushButton("Clear")
        self.lbl_count = QLabel("Tổng số tin nhắn: 0")
        self.lbl_status = QLabel("Not connected")
        self.lbl_status.setStyleSheet("color:#b00020;")

        top_layout.addWidget(self.btn_open)
        top_layout.addWidget(self.btn_clear)
        top_layout.addStretch()
        top_layout.addWidget(self.lbl_count)
        top_layout.addWidget(self.lbl_status)

        # central: QWebEngineView to render HTML
        self.web = QWebEngineView()
        # load current log file
        self.reload_view()

        # main layout
        v = QVBoxLayout()
        v.addLayout(top_layout)
        v.addWidget(self.web)
        self.setLayout(v)

        # signals
        self.btn_open.clicked.connect(self.open_log)
        self.btn_clear.clicked.connect(self.clear_display)
        signals.new_message.connect(self.on_new_message)
        signals.set_connected.connect(self.on_set_connected)
        signals.update_count.connect(self.on_update_count)

        # internal HTML buffer for GUI (header + appended entries)
        self.gui_body = ""  # will be headerless body; final = HTML_HEADER + gui_body + HTML_FOOTER
        # preload existing log's body to GUI to preserve previous logs in display:
        try:
            with open(HTML_LOG_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            # remove header & footer if present to reuse body
            if content.startswith(HTML_HEADER):
                body = content[len(HTML_HEADER):]
                if body.endswith(HTML_FOOTER):
                    body = body[:-len(HTML_FOOTER)]
                self.gui_body = body
        except Exception:
            self.gui_body = ""

        # ensure web shows current content
        self.set_web_html()

    def set_web_html(self):
        full = HTML_HEADER + self.gui_body + HTML_FOOTER
        # QWebEngineView.setHtml must be called on GUI thread (we are)
        self.web.setHtml(full)

    def reload_view(self):
        # show file content if present (used initially)
        if os.path.exists(HTML_LOG_FILE):
            # load file into web view
            with open(HTML_LOG_FILE, "r", encoding="utf-8") as f:
                html_content = f.read()
            self.web.setHtml(html_content)
        else:
            self.web.setHtml(HTML_HEADER + HTML_FOOTER)

    def open_log(self):
        path = os.path.abspath(HTML_LOG_FILE)
        if os.path.exists(path):
            # open in default browser
            if sys.platform.startswith("win"):
                os.startfile(path)
            else:
                import webbrowser
                webbrowser.open(f"file://{path}")
        else:
            QMessageBox.warning(self, "Lỗi", f"Không tìm thấy file: {path}")

    def clear_display(self):
        # keep file log intact; only clear GUI display
        self.gui_body = ""
        self.set_web_html()

    def on_new_message(self, sender, channel, message, translated):
        """
        This slot is executed in GUI thread. Append new entry to both GUI buffer and update web view.
        message & translated are plain text (may contain markdown/newlines) – convert here to html.
        """
        # detect mention color handled by css class "mention" assigned below
        # Note: message may contain HTML-sensitive chars; we escape then convert markdown to HTML
        # but using markdown on escaped text is safe: convert markdown -> html tokens
        # then append to gui_body and setHtml.
        # Decide css class based on presence of @MY_USERNAME in message (already detected upstream too).
        is_personal = (f"@{MY_USERNAME.lower()}" in (message or "").lower())
        css_class = "mention" if is_personal else "normal"
        safe_text = html_lib.escape(message or "")
        safe_trans = html_lib.escape(translated or "")
        html_text = markdown(safe_text, extensions=["fenced_code", "tables"])
        html_trans = markdown(safe_trans, extensions=["fenced_code", "tables"]) if safe_trans else ""
        entry = (
            f"<div class='msg {'mention' if css_class=='mention' else ''}'>"
            f"<div class='timestamp'>[{html_lib.escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}]</div>"
            f"<div><span class='sender'>{html_lib.escape(sender)}</span> "
            f"in <span class='channel'>{html_lib.escape(channel)}</span></div>"
            f"<div class='content'>{html_text}</div>"
        )
        if html_trans:
            entry += f"<div class='translated'>{html_trans}</div>"
        entry += "</div>\n"

        # append to GUI buffer
        self.gui_body += entry
        # update view
        self.set_web_html()
        # also append to file (append_html handles markdown+escape)
        append_html(sender, channel, message, css_class=("mention" if css_class=="mention" else "normal"), translated=translated)

    def on_set_connected(self, ok: bool):
        if ok:
            self.lbl_status.setText("Connected")
            self.lbl_status.setStyleSheet("color:#0b8043;")
        else:
            self.lbl_status.setText("Not connected")
            self.lbl_status.setStyleSheet("color:#b00020;")

    def on_update_count(self, count: int):
        self.lbl_count.setText(f"Tổng số tin nhắn: {count}")

# ---------------- WebSocket client (runs in background thread) ----------------
class WSClient:
    def __init__(self):
        self.ws = None
        self.msg_count = 0

    def start(self):
        def run():
            self.ws = websocket.WebSocketApp(
                WS_URL,
                header=[f"Cookie: MMUSERID={MMUSERID}; MMAUTHTOKEN={MMAUTHTOKEN}"],
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )
            # run_forever is blocking; it's inside thread
            self.ws.run_forever()
        t = threading.Thread(target=run, daemon=True)
        t.start()

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
        except Exception:
            return
        if data.get("event") != "posted":
            return
        try:
            post = json.loads(data["data"]["post"])
        except Exception:
            return
        channel_id = post.get("channel_id")
        if channel_id not in WATCH_CHANNELS:
            return
        user_id = post.get("user_id", "unknown")
        sender = USER_MAP.get(user_id, user_id)
        channel_name = CHANNEL_MAP.get(channel_id, channel_id)
        raw_text = post.get("message", "")

        # detect mentions
        is_personal = f"@{MY_USERNAME.lower()}" in (raw_text or "").lower()
        is_channel = any(k in (raw_text or "").lower() for k in ("@channel","@here","@all"))
        css_class = "mention" if is_personal else "normal"

        # call translate if configured
        translated = call_gemini_translate(raw_text, target_language="vi") if (API_KEY and GEMINI_URL) else ""

        # emit signal to GUI (sender, channel, message, translated)
        signals.new_message.emit(sender, channel_name, raw_text, translated)

        # update count
        self.msg_count += 1
        signals.update_count.emit(self.msg_count)

        # notify if mention/channel mention
        if is_personal or is_channel:
            title = f"Mention từ {sender}" if is_personal else f"Channel mention trong #{channel_name}"
            self.notify(title, raw_text)

    def notify(self, title, message):
        # Windows clickable toast
        if TOASTER is not None:
            try:
                TOASTER.show_toast(title, message, duration=5, threaded=True, callback_on_click=bring_to_front)
                return
            except Exception:
                pass
        if plyer_notification:
            try:
                plyer_notification.notify(title=title, message=message, timeout=5)
            except Exception:
                pass

    def on_error(self, ws, error):
        signals.set_connected.emit(False)

    def on_close(self, ws, close_status_code, close_msg):
        signals.set_connected.emit(False)

    def on_open(self, ws):
        # send authentication challenge
        try:
            auth = {"seq": 1, "action": "authentication_challenge", "data": {"token": MMAUTHTOKEN}}
            ws.send(json.dumps(auth))
        except Exception:
            pass
        signals.set_connected.emit(True)

# ---------------- Main entry ----------------
def main():
    app = QApplication(sys.argv)
    # instantiate GUI and background WS
    win = MainWindow()
    wsclient = WSClient()
    wsclient.start()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
