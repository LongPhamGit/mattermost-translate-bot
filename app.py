from flask import Flask, request
from deep_translator import GoogleTranslator
from datetime import datetime
import os

app = Flask(__name__)

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

@app.route('/translate', methods=['POST'])
def translate():
    text = request.form.get('text')
    user = request.form.get('user_name')
    channel = request.form.get('channel_name')

    if not text:
        return "Không có nội dung", 200

    if "@pnblong" not in text and "@channel" not in text and "@all" not in text:
        return "Không chứa mention hợp lệ", 200

    try:
        translated = GoogleTranslator(source='auto', target='vi').translate(text)

        append_log_to_html(text, translated, user, channel)

        # Trả về nội dung bản dịch cho người gửi (Postman hoặc console)
        message = f"""📩 Mention từ @{user} tại #{channel}:\n> {text}\n\n🈶 Dịch: {translated}"""
        return message, 200

    except Exception as e:
        return f"❌ Lỗi xử lý: {e}", 500

@app.route('/logs', methods=['GET'])
def view_logs():
    if not os.path.exists(HTML_LOG):
        return "<h3>Chưa có bản dịch nào.</h3>"
    with open(HTML_LOG, 'r', encoding='utf-8') as f:
        return f.read()

if __name__ == '__main__':
    init_html_file()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
