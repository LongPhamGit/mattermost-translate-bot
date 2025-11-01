# ws_client.py  (phiên bản đầy đủ phần quan trọng)
import json
import threading
import time
import websocket
from collections import deque

from PyQt6.QtCore import Qt

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

        # target language for translation (default 'vi')
        self.target_lang = "vi"

        # guard to prevent multiple start threads
        self._started = False

        # ---- runtime watch list (áp dụng ngay khi Settings thay đổi) ----
        self.watch_channels = set(WATCH_CHANNELS or [])

        # remember seen messages to avoid duplicates on reconnect / multi-clients
        self._seen_ids = set()
        self._seen_ids_order = deque(maxlen=1000)
        self._seen_hash = set()
        self._seen_hash_order = deque(maxlen=1000)

        # focus-aware notification gates
        self._app_started_ms = int(time.time() * 1000)
        self._last_focus_ms = 0
        self._connected_monotonic = 0.0
        self._FOCUS_BUFFER_MS = 2000
        self._RECONNECT_WARMUP_SEC = 2.0

        # Signals
        signals.reset_count.connect(self._on_reset_count, type=Qt.ConnectionType.UniqueConnection)
        signals.translate_lang_changed.connect(self._on_lang_changed, type=Qt.ConnectionType.UniqueConnection)
        signals.clicked.connect(self._on_user_focus, type=Qt.ConnectionType.UniqueConnection)

        # 🔔 NEW: nhận cập nhật WATCH_CHANNELS
        signals.watch_channels_changed.connect(self._on_watch_channels_changed, type=Qt.ConnectionType.UniqueConnection)

    # ===== slots from signals_bus =====
    def _on_reset_count(self):
        self.msg_count = 0
        signals.update_count.emit(0)

    def _on_lang_changed(self, code: str):
        self.target_lang = code if code in ("vi", "en", "ja", "id") else "vi"

    def _on_user_focus(self):
        self._last_focus_ms = int(time.time() * 1000)

    # 🔔 NEW
    def _on_watch_channels_changed(self, ids: list):
        try:
            newset = set(ids or [])
            self.watch_channels = newset
        except Exception:
            pass

    # ===== lifecycle =====
    def start(self):
        if self._started:
            return
        self._started = True
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

    # ===== WebSocket callbacks =====
    def on_open(self, ws):
        try:
            auth = {"seq": 1, "action": "authentication_challenge", "data": {"token": MMAUTHTOKEN}}
            ws.send(json.dumps(auth))
        except Exception:
            pass
        self._connected_monotonic = time.monotonic()
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
        # 🔔 dùng runtime watch list thay vì hằng số
        if channel_id not in self.watch_channels:
            return

        post_id = post.get("id")
        if post_id:
            if post_id in self._seen_ids:
                return
            self._seen_ids.add(post_id)
            self._seen_ids_order.append(post_id)
            if len(self._seen_ids_order) > self._seen_ids_order.maxlen:
                old = self._seen_ids_order.popleft()
                self._seen_ids.discard(old)
        else:
            key = (post.get("user_id", ""), post.get("channel_id", ""), post.get("message", ""))
            if key in self._seen_hash:
                return
            self._seen_hash.add(key)
            self._seen_hash_order.append(key)
            if len(self._seen_hash_order) > self._seen_hash_order.maxlen:
                oldk = self._seen_hash_order.popleft()
                self._seen_hash.discard(oldk)

        user_id = post.get("user_id", "unknown")
        sender = USER_MAP.get(user_id, user_id)
        channel_name = CHANNEL_MAP.get(channel_id, channel_id)
        raw_text = (post.get("message", "") or "").strip()

        lower = raw_text.lower()
        is_personal = f"@{MY_USERNAME.lower()}" in lower
        is_channel = any(k in lower for k in ("@channel", "@here", "@all"))

        # Translate
        if API_KEY and GEMINI_URL:
            try:
                translated = call_gemini_translate(raw_text, target_language=self.target_lang)
            except Exception:
                translated = ""
        else:
            translated = ""

        signals.new_message.emit(sender, channel_name, raw_text, translated)
        self.msg_count += 1
        signals.update_count.emit(self.msg_count)

        try:
            post_ms = int(post.get("create_at") or 0)
        except Exception:
            post_ms = 0
        if post_ms <= 0:
            post_ms = int(time.time() * 1000)

        baseline_ms = max(self._app_started_ms, self._last_focus_ms)
        is_old_vs_focus = post_ms < (baseline_ms - self._FOCUS_BUFFER_MS)
        just_connected = (time.monotonic() - self._connected_monotonic) < self._RECONNECT_WARMUP_SEC

        should_notify = False
        if not is_old_vs_focus:
            if is_personal:
                should_notify = True
                title = f"Mention từ {sender} trong #{channel_name}"
            elif is_channel:
                should_notify = True
                title = f"Channel mention trong #{channel_name}"

        if just_connected and is_old_vs_focus:
            should_notify = False

        if should_notify:
            self.notify(title, raw_text)

    def on_error(self, ws, error):
        signals.set_connected.emit(False)

    def on_close(self, ws, close_status_code, close_msg):
        signals.set_connected.emit(False)

    def notify(self, title, message):
        send_clickable_toast(title, message)
