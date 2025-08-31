# html_log.py
import os
import html as html_lib
from datetime import datetime
from markdown import markdown

from config_loader import HTML_LOG_FILE

# ---------------- HTML header/footer ----------------
MAX_LOG_BYTES = 5 * 1024 * 1024
ROTATE_TARGET_RATIO = 0.9

HTML_HEADER = """<html><head><meta charset='utf-8'>
<style>
body {
    font-family: Arial, sans-serif;
    font-size:14px;
    background:#ffffff;   /* nền trắng tổng thể */
    margin:20px;
}
.container {max-width:1000px; margin:0 auto; height:auto;}
.msg {
    margin:12px 0;
    padding:12px 14px;
    border:1px solid #d0e3f0;
    border-radius:8px;
    background:#eaf4fc;   /* xanh nhạt mặc định */
    box-shadow:0 1px 2px rgba(0,0,0,0.05);
    overflow:hidden;      /* CHỐNG TRÀN mép khung */
}
.msg:nth-child(even){background:#f0f8ff;}  /* xanh nhạt xen kẽ */

.msg.mention {
    background:#fff4e5;   /* cam nhạt khi có mention */
    border:1px solid #f5c890;
}

.timestamp {color:#666; font-size:12px; margin-bottom:6px;}
.sender {font-weight:600; color:#0b8043;}
.channel {color:#3367d6; font-style:italic;}
.content {
    margin-top:6px;
    color:#111;
    line-height:1.4;
    white-space:normal;
    word-wrap:break-word;   /* hỗ trợ trình duyệt cũ */
    overflow-wrap:anywhere; /* bẻ dòng chuỗi dài, URL */
    word-break:break-word;  /* fallback thêm */
}
.content a {
    overflow-wrap:anywhere;
    word-break:break-word;
}

pre, code {
    white-space: pre-wrap;  /* bẻ dòng trong code */
    overflow-wrap:anywhere;
    word-break:break-word;
}

.translated {
    margin-top:8px;
    padding-left:12px;
    border-left:3px solid #eee;
    font-style:italic;
    color:#555;
    white-space:normal;
    overflow-wrap:anywhere;
    word-break:break-word;
}
</style></head><body><div class="container">\n"""

HTML_FOOTER = "</div></body></html>\n"


def init_html_log():
    """Tạo file log HTML nếu chưa có"""
    if not os.path.exists(HTML_LOG_FILE):
        with open(HTML_LOG_FILE, "w", encoding="utf-8") as f:
            f.write(HTML_HEADER + HTML_FOOTER)


def rotate_html_log_if_needed():
    """Xoay log khi vượt quá dung lượng cho phép"""
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
    """Thêm một entry mới vào log HTML"""
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


# Khởi tạo file log nếu chưa tồn tại
init_html_log()
