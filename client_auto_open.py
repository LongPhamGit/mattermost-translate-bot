# client_auto_open.py
# Chạy file này để kết nối Socket.IO server và tự động mở/ghi log HTML khi có tin mới.
import socketio
import os
import webbrowser
from datetime import datetime

# ---- CẤU HÌNH ----
SERVER_URL = "https://mattermost-translate-bot.onrender.com"  # đổi sang URL của bạn
HTML_LOG = "translated_log.html"
AUTO_OPEN_ON_FIRST = True   # True: mở file HTML khi nhận tin đầu tiên
META_REFRESH_SECONDS = 5    # trang sẽ tự reload mỗi 5 giây

# ---- TẠO FILE HTML (nếu chưa có) ----
def init_html_file():
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

# ---- GHI LOG ----
def append_log_to_html(original, translated, sender, channel):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html_snip = f"""
<div class="entry">
  <div class="timestamp">🕒 {timestamp}</div>
  <b>👤 @{sender}</b> tại <code>#{channel}</code>
  <div class="original">💬 <b>Gốc:</b> {escape_html(original)}</div>
  <div class="translated">🈶 <b>Dịch:</b> {escape_html(translated)}</div>
</div>
"""
    # Append before closing </body></html>
    # Read file, insert html_snip before last </body>
    with open(HTML_LOG, "r", encoding="utf-8") as f:
        content = f.read()
    # if </body> not found (unexpected), append at end
    idx = content.rfind("</body>")
    if idx == -1:
        new = content + html_snip
    else:
        new = content[:idx] + html_snip + content[idx:]
    with open(HTML_LOG, "w", encoding="utf-8") as f:
        f.write(new)

def escape_html(s):
    if s is None:
        return ""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&#39;"))

# ---- WebSocket client ----
sio = socketio.Client(reconnection=True, reconnection_attempts=5, reconnection_delay=2)
_first_opened = False

@sio.event
def connect():
    print("✅ Connected to server.")

@sio.event
def disconnect():
    print("❌ Disconnected from server.")

@sio.on("new_message")
def on_new_message(data):
    global _first_opened
    print("\n📩 New message received:")
    print(f"  from: @{data.get('user')}  channel: #{data.get('channel')}")
    print(f"  original: {data.get('original')}")
    print(f"  translated: {data.get('translated')}\n")

    # append to HTML
    append_log_to_html(data.get('original',''), data.get('translated',''), data.get('user',''), data.get('channel',''))

    # open in browser on first message (or if file not open)
    if AUTO_OPEN_ON_FIRST and not _first_opened:
        _first_opened = True
        path = os.path.abspath(HTML_LOG)
        file_url = "file://" + path
        try:
            webbrowser.open_new_tab(file_url)
            print(f"🔎 Opened log in browser: {file_url}")
        except Exception as e:
            print("⚠️ Could not open browser automatically:", e)

# ---- main ----
if __name__ == "__main__":
    init_html_file()
    print(f"🔌 Connecting to {SERVER_URL} ...")
    sio.connect(SERVER_URL)
    sio.wait()
