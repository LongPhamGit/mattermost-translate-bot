from flask import Flask, request
from deep_translator import GoogleTranslator
from datetime import datetime
import os
import platform
import subprocess

app = Flask(__name__)

HTML_LOG = "translated_log.html"

def init_html_file():
    if not os.path.exists(HTML_LOG):
        with open(HTML_LOG, "w", encoding="utf-8") as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Translated Messages Log</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }
        .entry { background: white; padding: 15px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .timestamp { font-size: 12px; color: #888; }
        .user-channel { font-weight: bold; }
        .original { color: #333; margin-top: 10px; }
        .translated { color: green; margin-top: 10px; font-weight: bold; }
    </style>
</head>
<body>
    <h1>📘 Dịch tin nhắn Mattermost</h1>
""")

def append_log_to_html(original, translated, user, channel):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html_entry = f"""
    <div class="entry">
        <div class="timestamp">🕒 {timestamp}</div>
        <div class="user-channel">👤 @{user} tại #{channel}</div>
        <div class="original">💬 <strong>Gốc:</strong> {original}</div>
        <div class="translated">🈶 <strong>Dịch:</strong> {translated}</div>
    </div>
    """

    with open(HTML_LOG, "a", encoding="utf-8") as f:
        f.write(html_entry)

    open_log_file()

def open_log_file():
    abs_path = os.path.abspath(HTML_LOG)
    try:
        if platform.system() == "Windows":
            os.startfile(abs_path)
        elif platform.system() == "Darwin":
            subprocess.call(["open", abs_path])
        else:
            subprocess.call(["xdg-open", abs_path])
    except Exception as e:
        print(f"Lỗi mở file HTML: {e}")

@app.route('/translate', methods=['POST'])
def translate():
    text = request.form.get('text')
    user = request.form.get('user_name')
    channel = request.form.get('channel_name')

    if "@pnblong" not in text and "@channel" not in text and "@all" not in text:
        return "Không có mention phù hợp", 200

    try:
        translated = GoogleTranslator(source='auto', target='vi').translate(text)
        append_log_to_html(text, translated, user, channel)
        return "✅ Đã dịch và mở HTML", 200
    except Exception as e:
        return f"❌ Lỗi dịch: {e}", 500

if __name__ == '__main__':
    init_html_file()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
