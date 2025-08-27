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
from tkinter import messagebox

# =============== Notifications (Windows click-to-open supported) ===============
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

# ================= Load config (giữ nguyên cách xử lý) =================
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

SERVER_URL      = config.get("SERVER_URL", "http://localhost:8065")
WS_URL          = config.get("WS_URL", "ws://localhost:8065/api/v4/websocket")
MMUSERID        = config.get("MMUSERID", "")
MMAUTHTOKEN     = config.get("MMAUTHTOKEN", "")
MY_USERNAME     = config.get("MY_USERNAME", "lpham")
WATCH_CHANNELS  = config.get("WATCH_CHANNELS", [])
CHANNEL_MAP     = config.get("_comment", {})  # id -> name
USER_MAP        = config.get("USER_MAP", {})  # id -> username
API_KEY         = config.get("API_KEY", "")
GEMINI_URL      = config.get("GEMINI_URL", "")
HTML_LOG_FILE   = config.get("HTML_LOG", "messages.html")

cookies = {
    "MMUSERID": MMUSERID,
    "MMAUTHTOKEN": MMAUTHTOKEN
}

# ================== HTML Log Init + Rotation (5MB) ==================
MAX_LOG_BYTES = 5 * 1024 * 1024  # 5MB
ROTATE_TARGET_RATIO = 0.9        # cắt đến ~90% ngưỡng để giảm tần suất

def init_html_log():
    """Tạo file HTML log với CSS nếu chưa tồn tại (design đẹp hơn)."""
    if not os.path.exists(HTML_LOG_FILE):
        with open(HTML_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("""<html><head><meta charset='utf-8'>
<style>
body {font-family: Arial, sans-serif; font-size:14px; background:#f4f6f8; margin:20px;}
.msg {margin:12px auto; padding:10px 14px; border:1px solid #e0e0e0; 
      border-radius:8px; max-width:800px; background:#fff; box-shadow:0 1px 3px rgba(0,0,0,0.08);}
.msg:nth-child(even){background:#fdfdfd;}
.timestamp {color:#555; font-size:12px;}
.sender {font-weight:bold; color:#0b8043;}
.channel {color:#3367d6;}
.content {margin-top:6px; color:#111; line-height:1.4;}
.mention {color:#b00020; font-weight:bold;}
.translated {margin-top:6px; padding-left:12px; border-left:3px solid #e0e0e0;
             font-style:italic; color:#555;}
</style></head><body>\n""")

def rotate_html_log_if_needed():
    """Nếu file log > 5MB, xóa bớt entries cũ, giữ lại CSS header."""
    try:
        if not os.path.exists(HTML_LOG_FILE):
            return
        size = os.path.getsize(HTML_LOG_FILE)
        if size <= MAX_LOG_BYTES:
            return

        with open(HTML_LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        split_marker = "</style></head><body>"
        if split_marker in content:
            head, rest = content.split(split_marker, 1)
            head = head + split_marker + "\n"
        else:
            head, rest = "", content

        parts = rest.split("<div class='msg")
        if len(parts) <= 1:
            return

        prefix = parts[0]
        blocks = ["<div class='msg" + p for p in parts[1:]]

        target_size = int(MAX_LOG_BYTES * ROTATE_TARGET_RATIO)
        kept = []
        for i in range(len(blocks)-1, -1, -1):
            kept.append(blocks[i])
            new_body = prefix + "".join(reversed(kept))
            new_content = head + new_body
            if len(new_content.encode("utf-8")) >= target_size:
                break

        with open(HTML_LOG_FILE, "w", encoding="utf-8") as f:
            f.write(head)
            f.write(prefix)
            f.write("".join(reversed(kept)))
    except Exception:
        pass

def append_html(sender, channel_name, text, css_class="normal", translated=""):
    rotate_html_log_if_needed()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # highlight phần content trong HTML bằng class 'mention' nếu css_class == 'mention'
    content_class = "mention" if css_class == "mention" else "content"
    with open(HTML_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(
            f"<div class='msg'>"
            f"<div class='timestamp'>[{html.escape(timestamp)}]</div>"
            f"<div><span class='sender'>{html.escape(sender)}</span> "
            f"trong <span class='channel'>{html.escape(channel_name)}</span></div>"
            f"<div class='{content_class}'>{html.escape(text)}</div>"
            f"<div class='translated'>{html.escape(translated)}</div>"
            f"</div>\n"
        )

init_html_log()

# ================= Gemini Translate =================
def call_gemini_translate(text: str, target_language: str = "vi") -> str:
    if not API_KEY or not GEMINI_URL:
        return "[Lỗi dịch Gemini]: Thiếu API_KEY hoặc GEMINI_URL trong config.json"
    prompt_text = f"Dịch sang tiếng {target_language}, giữ nguyên ý nghĩa: {text}"
    headers = {"Content-Type": "application/json", "X-goog-api-key": API_KEY}
    payload = {"contents":[{"parts":[{"text": prompt_text}]}]}
    try:
        resp = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return "🔁 " + data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f"[Lỗi dịch Gemini]: {e}"

# ================= GUI =================
root = tk.Tk()
root.title("Mattermost Monitor – Gemini Translate")
root.geometry("960x720")

# ---- bring GUI to front ----
def bring_to_front():
    try:
        root.deiconify()
        root.lift()
        root.attributes("-topmost", True)
        root.after(400, lambda: root.attributes("-topmost", False))
        root.focus_force()
    except Exception:
        pass

# ---- Top frame ----
frame_top = tk.Frame(root)
frame_top.pack(fill=tk.X)

def open_html_log():
    path = os.path.abspath(HTML_LOG_FILE)
    if os.path.exists(path):
        webbrowser.open(f"file://{path}")
    else:
        messagebox.showerror("Lỗi", f"Không tìm thấy file log: {path}")

btn_open_log = tk.Button(frame_top, text="Mở file log HTML", command=open_html_log)
btn_open_log.pack(side=tk.LEFT, padx=8, pady=6)

msg_count = 0
lbl_count = tk.Label(frame_top, text=f"Tổng số tin nhắn: {msg_count}")
lbl_count.pack(side=tk.LEFT, padx=12)

conn_status_var = tk.StringVar(value="Not connected")
lbl_status = tk.Label(frame_top, textvariable=conn_status_var, fg="#b00020")
lbl_status.pack(side=tk.RIGHT, padx=12)

def set_connected(is_connected: bool):
    if is_connected:
        conn_status_var.set("Connected")
        lbl_status.config(fg="#0b8043")
    else:
        conn_status_var.set("Not connected")
        lbl_status.config(fg="#b00020")

def update_counter():
    lbl_count.config(text=f"Tổng số tin nhắn: {msg_count}")

# ---- Main text area ----
frame = tk.Frame(root)
frame.pack(fill=tk.BOTH, expand=True)

scrollbar = tk.Scrollbar(frame)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# NOTE: thêm padx/pady cho lề bên trong (đẹp)
text_widget = tk.Text(frame, font=("Segoe UI", 13), wrap=tk.WORD, padx=40, pady=20)
text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
text_widget.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=text_widget.yview)

# --- Tag styles: thêm 'header' và 'translated' tags ---
text_widget.tag_config("header", foreground="#333", font=("Segoe UI", 13, "bold"))
text_widget.tag_config("mention", foreground="#b00020")   # red for content when mention
text_widget.tag_config("normal", foreground="#111")       # black for content normally
text_widget.tag_config("translated", foreground="#555", font=("Segoe UI", 12, "italic"))

def add_log_gui(sender, channel_name, text, style_tag="normal", translated=""):
    """
    Chèn từng phần với tags ngay khi insert:
      - header: luôn dùng tag 'header' (không bị ảnh hưởng bởi tag content)
      - content: chèn với tag style_tag (mention hoặc normal)
      - translated: chèn với tag 'translated' (và style_tag nếu cần)
    Cách này tránh việc tag 'rò' sang các phần khác.
    """
    global msg_count
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # separator
    text_widget.insert(tk.END, "――――――――――――――――――――――――――――――――\n")
    # header (always header tag)
    header_line = f"[{timestamp}] Từ {sender} trong channel {channel_name}\n"
    text_widget.insert(tk.END, header_line, ("header",))

    # content (apply mention/normal tag)
    content_line = f"{text}\n"
    text_widget.insert(tk.END, content_line, (style_tag,))

    # translated (apply translated tag; also keep content color if mention)
    # if mention, we want translated to also be red AND italic; so apply both tags
    if style_tag == "mention":
        text_widget.insert(tk.END, f"{translated}\n\n", (style_tag, "translated"))
    else:
        text_widget.insert(tk.END, f"{translated}\n\n", ("translated",))

    text_widget.see(tk.END)

    # append to HTML log (keeps the previous behavior)
    append_html(sender, channel_name, text, css_class=style_tag, translated=translated)

    msg_count += 1
    update_counter()

# ================= Notifications =================
def notify_with_click(title: str, message: str):
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

# ================= Mentions detect =================
CHANNEL_MENTION_KEYS = ("@channel", "@here", "@all")
def detect_mentions(text: str):
    t = text.lower()
    is_personal = f"@{MY_USERNAME.lower()}" in t
    is_channel = any(k in t for k in CHANNEL_MENTION_KEYS)
    return is_personal, is_channel

# ================= WebSocket Callbacks =================
def on_message(ws, message):
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
    text = post.get("message", "")

    is_personal, is_channel = detect_mentions(text)
    style_tag = "mention" if is_personal else "normal"

    translated = call_gemini_translate(text, target_language="vi")
    add_log_gui(sender, channel_name, text, style_tag=style_tag, translated=translated)

    if is_personal or is_channel:
        title = f"Mention từ {sender}" if is_personal else f"Channel mention trong #{channel_name}"
        notify_with_click(title=title, message=text)

def on_error(ws, error):
    set_connected(False)

def on_close(ws, close_status_code, close_msg):
    set_connected(False)

def on_open(ws):
    set_connected(True)
    auth = {"seq": 1, "action": "authentication_challenge", "data": {"token": MMAUTHTOKEN}}
    try:
        ws.send(json.dumps(auth))
    except Exception:
        pass

# ================= Run WebSocket =================
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
