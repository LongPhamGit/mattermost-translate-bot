# ws_client.py
import json
import threading
import time
import websocket

from config_loader import (
    WS_URL, MY_USERNAME, WATCH_CHANNELS, USER_MAP, CHANNEL_MAP,
    MMUSERID, MMAUTHTOKEN, API_KEY, GEMINI_URL
)
from signals_bus import signals
from notifications import send_clickable_toast
from translate import call_gemini_translate


class WSClient:
    def __init__(self):
        self.ws = None
        self.msg_count = 0
        # reset tin nhắn chưa đọc
        signals.reset_count.connect(self._on_reset_count)

    def _on_reset_count(self):
        self.msg_count = 0
        signals.update_count.emit(0)

    def start(self):
        """Chạy client trong thread riêng; tự động reconnect mỗi 1s nếu rớt."""
        t = threading.Thread(target=self._run_loop, daemon=True)
        t.start()

    def _run_loop(self):
        while True:
            try:
                self.ws = websocket.WebSocketApp(
                    WS_URL,
                    header=[self._cookie_header()],
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                    on_open=self.on_open
                )
                self.ws.run_forever()
            except Exception:
                pass
            signals.set_connected.emit(False)
            time.sleep(1)

    def _cookie_header(self):
        return f"Cookie: MMUSERID={MMUSERID}; MMAUTHTOKEN={MMAUTHTOKEN}"

    # ============ WebSocket callbacks ============
    def on_open(self, ws):
        try:
            auth = {"seq": 1, "action": "authentication_challenge", "data": {"token": MMAUTHTOKEN}}
            ws.send(json.dumps(auth))
        except Exception:
            pass
        signals.set_connected.emit(True)

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
        is_channel = any(k in (raw_text or "").lower() for k in ("@channel", "@here", "@all"))
        translated = call_gemini_translate(raw_text, target_language="vi") if (API_KEY and GEMINI_URL) else ""

        signals.new_message.emit(sender, channel_name, raw_text, translated)

        self.msg_count += 1
        signals.update_count.emit(self.msg_count)

        if is_personal or is_channel:
            title = f"Mention từ {sender}" if is_personal else f"Channel mention trong #{channel_name}"
            self.notify(title, raw_text)

    def on_error(self, ws, error):
        signals.set_connected.emit(False)

    def on_close(self, ws, close_status_code, close_msg):
        signals.set_connected.emit(False)

    # ============ Notifications ============
    def notify(self, title, message):
        send_clickable_toast(title, message)
