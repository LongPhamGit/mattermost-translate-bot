from flask import Flask, request
from deep_translator import GoogleTranslator
from datetime import datetime
import os
import requests

app = Flask(__name__)

# === CẤU HÌNH WEBHOOK INCOMING ===
INCOMING_WEBHOOK_URL = "https://mattermost01.ssl.mdomain/hooks/yk9m43a7ypyfmm4acu6h47wkie"  # ← Thay bằng webhook thật

# === LOG HTML (TÙY CHỌN) ===
HTML_LOG = "translated_log.html"

def init_html_file():
    if not os.path.exists(HTML_LOG):
        with open(HTML_LOG, "w", encoding="utf-8") as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Translated Logs</title>
    <style>
        body { font-family: sans-serif; background: #f5f5f5; padding: 20px; }
        .entry { background: white; padding: 10px; margin-bottom: 10px; border-left: 5px solid #4caf50; }
        .timestamp { font-size: 12px; color: #999; }
        .original { margin-top: 10px; }
        .translated { color: green; margin-top: 5px; }
    </style>
</head>
<body>
<h2>📘 Lịch sử bản dịch</h2>
""")

def append_log_to_html(original, translated, sender, channel):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = f"""<div class="entry">
<div class="timestamp">🕒 {timestamp}</div>
<b>👤 @{sender}</b> tại <code>#{channel}</code>
<div class="original">💬 <b>Gốc:</b> {original}</div>
<div class="translated">🈶 <b>Dịch:</b> {translated}</div>
</div>
"""
    with open(HTML_LOG, "a", encoding="utf-8") as f:
        f.write(html)

# === GỬI VỀ WEBHOOK ===
def send_to_webhook(original, translated, sender, channel_name):
    message = f"""📩 **Mention từ @{sender} tại `#{channel_name}`**
> {original}

🈶 **Dịch:** {translated}"""
    payload = {
        "username": "TranslateBot",
        "text": message,
        "icon_emoji": "🈶"
    }
    try:
        requests.post(INCOMING_WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"❌ Lỗi gửi webhook: {e}")

# === ENDPOINT XỬ LÝ ===
@app.route('/translate', methods=['POST'])
def translate():
    text = request.form.get('text')
    user = request.form.get('user_name')
    channel = request.form.get('channel_name')

    if not text:
        return "No text", 200

    if "@pnblong" not in text and "@channel" not in text and "@all" not in text:
        return "Không chứa mention hợp lệ", 200

    try:
        translated = GoogleTranslator(source='auto', target='vi').translate(text)

        # Lưu log
        append_log_to_html(text, translated, user, channel)

        # Gửi về webhook
        send_to_webhook(text, translated, user, channel)

        return "✅ Đã dịch và gửi vào channel", 200
    except Exception as e:
        return f"❌ Lỗi xử lý: {e}", 500

if __name__ == '__main__':
    init_html_file()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
