import requests
import json
import websocket
import threading
import tkinter as tk
from datetime import datetime

CONFIG_FILE = "config.json"

# ================= Load config =================
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

SERVER_URL = config.get("SERVER_URL")
WS_URL = config.get("WS_URL")
MMUSERID = config.get("MMUSERID")
MMAUTHTOKEN = config.get("MMAUTHTOKEN")
MY_USERNAME = config.get("MY_USERNAME")
WATCH_CHANNELS = config.get("WATCH_CHANNELS", [])
CHANNEL_MAP = config.get("_comment", {})  # channel_id -> channel_name

cookies = {
    "MMUSERID": MMUSERID,
    "MMAUTHTOKEN": MMAUTHTOKEN
}

# ================= User cache =================
USER_CACHE = {}  # user_id -> username

def get_username(user_id):
    if user_id in USER_CACHE:
        return USER_CACHE[user_id]
    try:
        r = requests.get(f"{SERVER_URL}/api/v4/users/{user_id}", cookies=cookies)
        r.raise_for_status()
        user_info = r.json()
        username = user_info.get("username", user_id)
        USER_CACHE[user_id] = username
        return username
    except:
        return user_id

# ================= Auto update WATCH_CHANNELS if empty =================
if not WATCH_CHANNELS:
    print("WATCH_CHANNELS trống, lấy tự động từ server...")
    team_resp = requests.get(f"{SERVER_URL}/api/v4/users/me/teams", cookies=cookies)
    team_resp.raise_for_status()
    teams = team_resp.json()

    all_channel_ids = []
    comments = {}

    for t in teams:
        team_id = t["id"]

        ch_resp = requests.get(f"{SERVER_URL}/api/v4/users/me/teams/{team_id}/channels", cookies=cookies)
        ch_resp.raise_for_status()
        channels = ch_resp.json()
        for ch in channels:
            ch_id = ch["id"]
            ch_name = ch["name"]
            all_channel_ids.append(ch_id)
            comments[ch_id] = ch_name

    config["WATCH_CHANNELS"] = all_channel_ids
    config["_comment"] = comments

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

    WATCH_CHANNELS = all_channel_ids
    CHANNEL_MAP = comments
    print(f"Đã cập nhật WATCH_CHANNELS với {len(all_channel_ids)} channel_id")

# ================= GUI =================
root = tk.Tk()
root.title("Mattermost Monitor")
root.geometry("700x500")

frame = tk.Frame(root)
frame.pack(fill=tk.BOTH, expand=True)

scrollbar = tk.Scrollbar(frame)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set)
listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar.config(command=listbox.yview)

def add_log(sender, target, text, highlight=False):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    display_text = f"[{timestamp}] Từ {sender} đến {target}\n{text}"
    if highlight:
        listbox.insert(tk.END, display_text)
        listbox.itemconfig(tk.END, {'fg': 'red'})
    else:
        listbox.insert(tk.END, display_text)
    listbox.yview(tk.END)
    with open("messages.log", "a", encoding="utf-8") as f:
        f.write(display_text + "\n")

# ================= WebSocket =================
def on_message(ws, message):
    try:
        data = json.loads(message)
    except json.JSONDecodeError:
        return

    if data.get("event") == "posted":
        post = json.loads(data["data"]["post"])
        channel_id = post.get("channel_id")
        text = post.get("message", "")
        user_id = post.get("user_id", "")
        if channel_id in WATCH_CHANNELS:
            sender = get_username(user_id)
            if f"@{MY_USERNAME}" in text:
                target = MY_USERNAME
                highlight = True
            else:
                target = CHANNEL_MAP.get(channel_id, channel_id)
                highlight = False
            add_log(sender, target, text, highlight)

def on_error(ws, error):
    add_log("System", "WebSocket", f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    add_log("System", "WebSocket", "Connection closed")

def on_open(ws):
    add_log("System", "WebSocket", "Connection opened")
    auth = {"seq": 1, "action": "authentication_challenge", "data": {"token": MMAUTHTOKEN}}
    ws.send(json.dumps(auth))

headers = [f"Cookie: MMUSERID={MMUSERID}; MMAUTHTOKEN={MMAUTHTOKEN}"]

ws_app = websocket.WebSocketApp(
    WS_URL,
    header=headers,
    on_message=on_message,
    on_error=on_error,
    on_close=on_close,
    on_open=on_open
)

wst = threading.Thread(target=ws_app.run_forever)
wst.daemon = True
wst.start()

root.mainloop()
