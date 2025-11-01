import json
import os
import html
import platform
import threading
import webbrowser
from datetime import datetime

import requests
import websocket
import tkinter as tk

# --- Notifications (cross-platform + Windows click support)
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

CONFIG_FILE = "config.json"

# ================= Load config =================
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

SERVER_URL   = config.get("SERVER_URL", "http://localhost:8065")
WS_URL       = config.get("WS_URL", "ws://localhost:8065/api/v4/websocket")
MMUSERID     = config.get("MMUSERID", "")
MMAUTHTOKEN  = config.get("MMAUTHTOKEN", "")
MY_USERNAME  = config.get("MY_USERNAME", "lpham")
WATCH_CHANNELS = config.get("WATCH_CHANNELS", [])
CHANNEL_MAP    = config.get("_comment", {})  # id -> name
API_KEY     = config.get("API_KEY", "")
GEMINI_URL  = config.get("GEMINI_URL", "")
HTML_LOG_FILE = config.get("HTML_LOG", "messages.html")

cookies = {
    "MMUSERID": MMUSERID,
    "MMAUTHTOKEN": MMAUTHTOKEN
}

# ================= User cache =================
USER_CACHE = {}  # user_id -> username

def get_username(user_id: str) -> str:
    if user_id in USER_CACHE:
        return USER_CACHE[user_id]
    try:
        r = requests.get(f"{SERVER_URL}/api/v4/users/{user_id}", cookies=cookies, timeout=10)
        r.raise_for_status()
        username = r.json().get("username", user_id)
        USER_CACHE[user_id] = username
        return username
    except Exception:
        return user_id

# ================= Gemini Translate =================
def call_gemini_translate(text: str, target_language: str = "vi") -> str:
    if not API_KEY or not GEMINI_URL:
        return "[Lỗi dịch Gemini]: Thiếu API_KEY hoặc GEMINI_URL trong config.json"
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
        resp = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f"[Lỗi dịch Gemini]: {e}"

# ================= Tự động lấy WATCH_CHANNELS nếu trống =================
def ensure_watch_channels():
    global WATCH_CHANNELS, CHANNEL_MAP, config
    if WATCH_CHANNELS:
        return
    print("WATCH_CHANNELS trống, đang lấy từ server...")
    try:
        teams = requests.get(f"{SERVER_URL}/api/v4/users/me/teams", cookies=cookies, timeout=15).json()
        all_channel_ids = {}
        for t in teams:
            team_id = t["id"]
            channels = requests.get(
                f"{SERVER_URL}/api/v4/users/me/teams/{team_id}/channels",
                cookies=cookies, timeout=20
            ).json()
            for ch in channels:
                all_channel_ids[ch["id"]] = ch.get("name", ch["id"])
        WATCH_CHANNELS = list(all_channel_ids.keys())
        CHANNEL_MAP = all_channel_ids
        config["WATCH_CHANNELS"] = WATCH_CHANNELS
        config["_comment"] = CHANNEL_MAP
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        print(f"Đã cập nhật WATCH_CHANNELS với {len(WATCH_CHANNELS)} channel_id")
    except Exception as e:
        print("Không thể tự động lấy channel:", e)

ensure_watch_channels()

# ================= HTML Log Init =================
def init_html_log():
    if not os.path.exists(HTML_LOG_FILE):
        with open(HTML_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("<html><head><meta charset='utf-8'><style>")
            f.write("body {font-family: Arial; font-size:14px; background:#f9f9f9;}")
            f.write(".mention {color:#b00020; font-weight:bold;}")
            f.write(".normal {color:#111;}")
            f.write(".msg {margin:10px 0; padding:8px 10px; border:1px solid #e5e5e5; border-radius:8px; background:#fff;}")
            f.write("</style></head><body>\n")

init_html_log()

def append_html(sender, channel_name, text, css_class="normal", translated=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(HTML_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(
            f"<div class='msg {css_class}'><b>[{html.escape(timestamp)}]</b> "
            f"Từ {html.escape(sender)} trong {html.escape(channel_name)}<br>"
            f"{html.escape(text)}<br>{html.escape(translated)}</div>\n"
        )

# ================= GUI =================
root = tk.Tk()
root.title("Mattermost Monitor – Gemini Translate")
root.geometry("920x680")

# Bring-to-front helper
def bring_to_front():
    try:
        root.deiconify()
        root.lift()
        root.attributes("-topmost", True)
        root.after(500, lambda: root.attributes("-topmost", False))
        root.focus_force()
    except Exception:
        pass

# Top frame: nút mở log + tổng số tin
frame_top = tk.Frame(root)
frame_top.pack(fill=tk.X)

def open_html_log():
    path = os.path.abspath(HTML_LOG_FILE)
    webbrowser.open(f"file://{path}")

btn_open_log = tk.Button(frame_top, text="Mở file log HTML", command=open_html_log)
btn_open_log.pack(side=tk.LEFT, padx=8, pady=6)

msg_count = 0
lbl_count = tk.Label(frame_top, text=f"Tổng số tin nhắn: {msg_count}")
lbl_count.pack(side=tk.LEFT, padx=12)

def update_counter():
    lbl_count.config(text=f"Tổng số tin nhắn: {msg_count}")

# Frame chính
frame = tk.Frame(root)
frame.pack(fill=tk.BOTH, expand=True)

scrollbar = tk.Scrollbar(frame)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

text_widget = tk.Text(frame, font=("Segoe UI", 13), wrap=tk.WORD)
text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
text_widget.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=text_widget.yview)

# Tag styles: mention cá nhân đỏ, còn lại đen
text_widget.tag_config("mention", foreground="#b00020")  # đỏ
text_widget.tag_config("normal", foreground="#111")      # đen

def add_log_gui(sender, channel_name, text, style_tag="normal", translated=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    block = f"[{timestamp}] Từ {sender} trong {channel_name}\n{text}\n{translated}\n\n"
    start_idx = text_widget.index(tk.END)
    text_widget.insert(tk.END, block)
    end_idx = text_widget.index(tk.END)
    text_widget.tag_add(style_tag, start_idx, end_idx)
    text_widget.see(tk.END)

    append_html(sender, channel_name, text, css_class=style_tag, translated=translated)

def notify_with_click(title: str, message: str, on_click=None):
    if TOASTER is not None:
        try:
            TOASTER.show_toast(
                title, message,
                duration=5, threaded=True,
                callback_on_click=on_click if on_click else bring_to_front
            )
            return
        except Exception:
            pass
    if plyer_notification:
        try:
            plyer_notification.notify(title=title, message=message, timeout=5)
        except Exception:
            pass

# ================= Detect mentions =================
CHANNEL_MENTION_KEYS = ("@channel", "@here", "@all")

def detect_mentions(text: str):
    t = text.lower()
    is_personal = f"@{MY_USERNAME.lower()}" in t
    is_channel = any(k in t for k in CHANNEL_MENTION_KEYS)
    return is_personal, is_channel

# ================= WebSocket callbacks =================
def on_message(ws, message):
    global msg_count
    try:
        data = json.loads(message)
    except Exception:
        return

    if data.get("event") == "posted":
        try:
            post = json.loads(data["data"]["post"])
        except Exception:
            return

        channel_id = post.get("channel_id")
        text = post.get("message", "")
        user_id = post.get("user_id", "")

        if channel_id not in WATCH_CHANNELS:
            return

        sender = get_username(user_id)
        channel_name = CHANNEL_MAP.get(channel_id, channel_id)

        is_personal, is_channel = detect_mentions(text)

        # Nếu tin nhắn gửi trực tiếp đến tôi -> tất cả đỏ
        style_tag = "mention" if is_personal else "normal"

        translated = call_gemini_translate(text, target_language="vi")

        msg_count += 1
        update_counter()

        add_log_gui(sender, channel_name, text, style_tag=style_tag, translated=translated)

        if is_personal or is_channel:
            title = f"Mention từ {sender}" if is_personal else f"Channel mention trong #{channel_name}"
            notify_with_click(title=title, message=text, on_click=bring_to_front)

def on_error(ws, error):
    add_log_gui("System", "system", f"WebSocket error: {error}", style_tag="normal")

def on_close(ws, close_status_code, close_msg):
    add_log_gui("System", "system", "WebSocket closed", style_tag="normal")

def on_open(ws):
    add_log_gui("System", "system", "WebSocket opened", style_tag="normal")
    auth = {"seq": 1, "action": "authentication_challenge", "data": {"token": MMAUTHTOKEN}}
    ws.send(json.dumps(auth))

# ================= WebSocket run =================
headers = [f"Cookie: MMUSERID={MMUSERID}; MMAUTHTOKEN={MMAUTHTOKEN}"]
ws_app = websocket.WebSocketApp(
    WS_URL,
    header=headers,
    on_message=on_message,
    on_error=on_error,
    on_close=on_close,
    on_open=on_open
)

threading.Thread(target=ws_app.run_forever, daemon=True).start()

# Start GUI
root.mainloop()
