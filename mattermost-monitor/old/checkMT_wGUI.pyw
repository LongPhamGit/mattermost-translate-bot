# mattermost_qt_webview_compact.py
import sys
import os
import json
import html as html_lib
import threading
from datetime import datetime

import requests
import websocket
from markdown import markdown

from PyQt6.QtCore import pyqtSignal, QObject, Qt, QTimer, QUrl
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QMessageBox, QSizePolicy
)
from PyQt6.QtGui import QFont, QDesktopServices
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage

# =============== Notifications (Windows click-to-open supported) ===============
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

# ---------------- Config load ----------------
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
CHANNEL_MAP     = config.get("_comment", {})
USER_MAP        = config.get("USER_MAP", {})
API_KEY         = config.get("API_KEY", "")
GEMINI_URL      = config.get("GEMINI_URL", "")
HTML_LOG_FILE   = config.get("HTML_LOG", "messages.html")

cookies = {"MMUSERID": MMUSERID, "MMAUTHTOKEN": MMAUTHTOKEN}

# ---------------- HTML header/footer ----------------
MAX_LOG_BYTES = 5 * 1024 * 1024
ROTATE_TARGET_RATIO = 0.9

HTML_HEADER = """<html><head><meta charset='utf-8'>
<style>
body {font-family: Arial, sans-serif; font-size:14px; background:#f4f6f8; margin:20px;}
.container {max-width:1000px; margin:0 auto; height:auto;}
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
        if HTML_HEADER in content:
            body = content.replace(HTML_HEADER, "").replace(HTML_FOOTER, "")
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

def call_gemini_translate(text: str, target_language: str = "vi") -> str:
    if not API_KEY or not GEMINI_URL:
        return ""
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

# ================== Mở link ngoài bằng browser hệ thống ==================
class ExternalLinkPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, isMainFrame):
        if nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            if url.scheme() in ("http", "https", "mailto"):
                QDesktopServices.openUrl(url)
                return False
        return super().acceptNavigationRequest(url, nav_type, isMainFrame)

    def createWindow(self, web_window_type):
        temp_page = QWebEnginePage(self.profile())
        def _open_external(u: QUrl):
            if u.isValid() and u.scheme() in ("http", "https", "mailto"):
                QDesktopServices.openUrl(u)
        temp_page.urlChanged.connect(_open_external)
        return temp_page

# ---------------- Signals ----------------
class Signals(QObject):
    new_message = pyqtSignal(str, str, str, str)  # sender, channel, message, translated
    set_connected = pyqtSignal(bool)
    update_count = pyqtSignal(int)
    clicked = pyqtSignal()  # <-- bridge cho click thông báo (thread-safe)

signals = Signals()  # Tạo trong main thread

# ============== Helper: gửi toast và emit signal vào Qt main thread ==============
def send_clickable_toast(title: str, message: str):
    """
    Gửi 1 toast (Windows). Khi click:
      - Emit signals.clicked() -> Qt tự dispatch vào main thread (QueuedConnection),
        rồi MainWindow xử lý mở GUI & scroll.
    """
    if TOASTER is not None:
        try:
            def _on_click():
                try:
                    # Emit từ thread khác được, Qt sẽ queue về main thread
                    signals.clicked.emit()
                except Exception:
                    pass
            # Sticky để kịp click; muốn tự tắt thì đổi duration=5
            TOASTER.show_toast(title, message, duration=None, threaded=True, callback_on_click=_on_click)
            return
        except Exception:
            pass
    # Fallback (không có callback click)
    if plyer_notification:
        try:
            plyer_notification.notify(title=title, message=message, timeout=5)
        except Exception:
            pass

# ---------------- MainWindow ----------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mattermost Monitor – WebEngine")
        self.resize(980, 760)

        # --------- TOP BAR ----------
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(2, 0, 2, 0)
        top_layout.setSpacing(4)

        font_btn = QFont("Arial", 12)
        font_label = QFont("Arial", 12)

        self.btn_open = QPushButton("Mở file log HTML")
        self.btn_open.setFont(font_btn)
        self.btn_open.setStyleSheet("padding:5px 12px;")

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setFont(font_btn)
        self.btn_clear.setStyleSheet("padding:5px 12px;")

        self.lbl_count = QLabel("Tổng số tin nhắn: 0")
        self.lbl_count.setFont(font_label)

        self.lbl_status = QLabel("Not connected")
        self.lbl_status.setFont(font_label)
        self.lbl_status.setStyleSheet("color:#b00020;")

        top_layout.addWidget(self.btn_open)
        top_layout.addWidget(self.btn_clear)
        top_layout.addStretch()
        top_layout.addWidget(self.lbl_count)
        top_layout.addWidget(self.lbl_status)

        top_widget = QWidget()
        top_widget.setLayout(top_layout)
        top_widget.setFixedHeight(36)
        top_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # --------- WEB VIEW ----------
        self.web = QWebEngineView()
        self.web.setPage(ExternalLinkPage(self.web))

        # GUI KHỞI ĐỘNG TRỐNG: không nạp nội dung cũ vào vùng log
        self.gui_body = ""          # chỉ hiển thị tin mới
        self.set_web_html()         # render trống (chỉ header/footer)

        # --------- MAIN LAYOUT ----------
        v = QVBoxLayout()
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)
        v.addWidget(top_widget)
        v.addWidget(self.web)
        self.setLayout(v)

        # Signals
        self.btn_open.clicked.connect(self.open_log)
        self.btn_clear.clicked.connect(self.clear_display)
        signals.new_message.connect(self.on_new_message)
        signals.set_connected.connect(self.on_set_connected)
        signals.update_count.connect(self.on_update_count)
        # Khi click vào thông báo -> mở GUI + scroll
        signals.clicked.connect(self._show_and_scroll_bottom, type=Qt.ConnectionType.QueuedConnection)

    # === Bring-to-front & scroll xuống cuối ===
    def _show_and_scroll_bottom(self):
        try:
            # Bỏ minimize nếu đang minimize
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
            # Bật on-top tạm để nổi lên trước
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.show()            # áp dụng flag
            self.raise_()
            self.activateWindow()
            QApplication.alert(self, 0)   # chớp taskbar

            # Tắt on-top sau 600ms để không làm phiền
            QTimer.singleShot(600, self._clear_on_top_flag)

            # Cuộn xuống cuối (container hoặc body)
            js = r"""
            (function(){
                var cont = document.querySelector('.container');
                if (cont) {
                    try { cont.scrollTop = cont.scrollHeight; } catch(e){}
                    try { if (cont.lastElementChild) cont.lastElementChild.scrollIntoView({behavior:'instant', block:'end'}); } catch(e){}
                } else {
                    try { window.scrollTo(0, document.body.scrollHeight); } catch(e){}
                }
                return true;
            })();
            """
            self.web.page().runJavaScript(js)
        except Exception:
            pass

    def _clear_on_top_flag(self):
        try:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.show()
        except Exception:
            pass

    def set_web_html(self):
        self.web.setHtml(HTML_HEADER + self.gui_body + HTML_FOOTER)

    def reload_view(self):
        # KHÔNG nạp file log vào GUI khi mở app
        self.set_web_html()

    def open_log(self):
        path = os.path.abspath(HTML_LOG_FILE)
        if os.path.exists(path):
            if sys.platform.startswith("win"):
                os.startfile(path)
            else:
                import webbrowser
                webbrowser.open(f"file://{path}")
        else:
            QMessageBox.warning(self, "Lỗi", f"Không tìm thấy file: {path}")

    def clear_display(self):
        self.gui_body = ""
        self.set_web_html()

    def on_new_message(self, sender, channel, message, translated):
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

        # Cập nhật GUI chỉ với tin mới
        self.gui_body += entry
        self.set_web_html()

        # Ghi file log như cũ
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

# ---------------- WebSocket Client ----------------
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

        is_personal = f"@{MY_USERNAME.lower()}" in (raw_text or "").lower()
        is_channel = any(k in (raw_text or "").lower() for k in ("@channel","@here","@all"))
        translated = call_gemini_translate(raw_text, target_language="vi") if (API_KEY and GEMINI_URL) else ""

        signals.new_message.emit(sender, channel_name, raw_text, translated)

        self.msg_count += 1
        signals.update_count.emit(self.msg_count)

        if is_personal or is_channel:
            title = f"Mention từ {sender}" if is_personal else f"Channel mention trong #{channel_name}"
            self.notify(title, raw_text)

    def notify(self, title, message):
        # 1 thông báo duy nhất; click => emit signal -> mở GUI + scroll
        send_clickable_toast(title, message)

    def on_error(self, ws, error):
        signals.set_connected.emit(False)

    def on_close(self, ws, close_status_code, close_msg):
        signals.set_connected.emit(False)

    def on_open(self, ws):
        try:
            auth = {"seq": 1, "action": "authentication_challenge", "data": {"token": MMAUTHTOKEN}}
            ws.send(json.dumps(auth))
        except Exception:
            pass
        signals.set_connected.emit(True)

# ---------------- Main ----------------
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    wsclient = WSClient()
    wsclient.start()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
