# main_window.py
import os
import html as html_lib
from datetime import datetime
from markdown import markdown

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QCheckBox,
    QMessageBox, QSizePolicy
)
from PyQt6.QtGui import QFont, QPainter, QBrush, QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView

from config_loader import HTML_LOG_FILE, MY_USERNAME
from signals_bus import signals
from html_log import HTML_HEADER, HTML_FOOTER, append_html
from webview_pages import ExternalLinkPage

# ===================== ToggleSwitch =====================
class ToggleSwitch(QCheckBox):
    """Toggle ON/OFF with thumb tròn trượt qua trái/phải"""
    def __init__(self, parent=None, checked=True):
        super().__init__(parent)
        self.setFixedSize(50, 28)
        self.setChecked(checked)
        self._thumb_x = 2
        self._anim = QPropertyAnimation(self, b"_thumb_pos", self)
        self._anim.setDuration(200)
        self._on_color = QColor("#2F3C56")   # navy
        self._off_color = QColor("#ffffff")   # trắng
        self.stateChanged.connect(self.animate_toggle)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background theo trạng thái
        bg_color = self._on_color if self.isChecked() else self._off_color
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), self.height()//2, self.height()//2)

        # Thumb
        thumb_radius = self.height() - 4
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawEllipse(self._thumb_x, 2, thumb_radius, thumb_radius)

    def animate_toggle(self):
        start = 2 if not self.isChecked() else self.width() - self.height() + 2
        end = self.width() - self.height() + 2 if self.isChecked() else 2
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()

    def _set_thumb_pos(self, pos):
        self._thumb_x = pos
        self.update()

    def _get_thumb_pos(self):
        return self._thumb_x

    _thumb_pos = property(_get_thumb_pos, _set_thumb_pos)

# ===================== MainWindow =====================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mattermost Checker")

        # ===================== BANNER =====================
        banner = QLabel("Mattermost Checker")
        banner_font = QFont("Segoe UI", 13, QFont.Weight.Bold)
        banner.setFont(banner_font)
        banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        banner.setFixedHeight(36)
        banner.setStyleSheet("""
            QLabel {
                color: #ffffff;
                background-color: #2F3C56;
                padding: 6px 10px;
                border-radius: 4px;
                letter-spacing: 0.3px;
            }
        """)

        font_btn = QFont("Arial", 12)
        font_label = QFont("Arial", 12)

        self.btn_open = QPushButton("Open HTML log file")
        self.btn_open.setFont(font_btn)
        self.btn_open.setStyleSheet("padding:5px 12px;")

        self.lbl_status = QLabel("Not connected")
        self.lbl_status.setFont(font_label)
        self.lbl_status.setStyleSheet("color:#b00020;")

        self.lbl_count = QLabel("Total messages: 0")
        self.lbl_count.setFont(font_label)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setFont(font_btn)
        self.btn_clear.setStyleSheet("padding:5px 12px;")

        # ===================== Toggle Switches =====================
        self.show_original_toggle = ToggleSwitch(checked=True)
        self.show_translated_toggle = ToggleSwitch(checked=True)

        lbl_original = QLabel("Show Original")
        lbl_translated = QLabel("Show Translated")
        lbl_original.setFont(font_label)
        lbl_translated.setFont(font_label)

        toggle_layout = QHBoxLayout()
        toggle_layout.addStretch(1)

        orig_layout = QHBoxLayout()
        orig_layout.setSpacing(6)
        orig_layout.addWidget(lbl_original)
        orig_layout.addWidget(self.show_original_toggle)
        toggle_layout.addLayout(orig_layout)

        toggle_layout.addSpacing(20)

        trans_layout = QHBoxLayout()
        trans_layout.setSpacing(6)
        trans_layout.addWidget(lbl_translated)
        trans_layout.addWidget(self.show_translated_toggle)
        toggle_layout.addLayout(trans_layout)
        toggle_layout.addStretch(1)

        # ===================== Layout top (Open, Status, Count+Clear) =====================
        left_layout = QHBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        left_layout.addWidget(self.btn_open)

        center_layout = QHBoxLayout()
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(4)
        center_layout.addWidget(self.lbl_status)

        right_layout = QHBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(self.lbl_count)
        right_layout.addWidget(self.btn_clear)

        top_layout = QVBoxLayout()
        top_layout.setContentsMargins(2, 0, 2, 0)
        top_layout.setSpacing(4)

        bar_layout = QHBoxLayout()
        bar_layout.addLayout(left_layout)
        bar_layout.addStretch(1)
        bar_layout.addLayout(center_layout)
        bar_layout.addStretch(1)
        bar_layout.addLayout(right_layout)

        top_layout.addLayout(bar_layout)
        top_layout.addLayout(toggle_layout)

        top_widget = QWidget()
        top_widget.setLayout(top_layout)
        top_widget.setFixedHeight(80)
        top_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # ===================== WEB VIEW =====================
        self.web = QWebEngineView()
        self.web.setPage(ExternalLinkPage(self.web))
        self.gui_body = ""
        self.set_web_html()

        # ===================== MAIN LAYOUT =====================
        v = QVBoxLayout()
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(8)
        v.addWidget(banner)
        v.addWidget(top_widget)
        v.addWidget(self.web)
        self.setLayout(v)
        self.resize(1000, 760)

        # ===================== SIGNALS =====================
        self.btn_open.clicked.connect(self.open_log)
        self.btn_clear.clicked.connect(self.clear_display_and_reset_count)
        signals.new_message.connect(self.on_new_message)
        signals.set_connected.connect(self.on_set_connected)
        signals.update_count.connect(self.on_update_count)
        signals.clicked.connect(self._show_and_scroll_bottom, type=Qt.ConnectionType.QueuedConnection)

    # ===================== WEB CONTENT =====================
    def set_web_html(self):
        self.web.setHtml(HTML_HEADER + self.gui_body + HTML_FOOTER)

    def open_log(self):
        path = os.path.abspath(HTML_LOG_FILE)
        try:
            if os.path.exists(path):
                if os.name == "nt":
                    os.startfile(path)
                else:
                    import webbrowser
                    webbrowser.open(f"file://{path}")
            else:
                QMessageBox.warning(self, "Error", f"File not found: {path}")
        except Exception:
            QMessageBox.warning(self, "Error", f"Cannot open file: {path}")

    def clear_display_and_reset_count(self):
        self.gui_body = ""
        self.set_web_html()
        signals.reset_count.emit()

    def on_new_message(self, sender, channel, message, translated):
        is_personal = (f"@{MY_USERNAME.lower()}" in (message or "").lower())
        css_class = "mention" if is_personal else "normal"
        safe_text = html_lib.escape(message or "")
        safe_trans = html_lib.escape(translated or "")
        html_text = markdown(safe_text, extensions=["fenced_code", "tables"])
        html_trans = markdown(safe_trans, extensions=["fenced_code", "tables"]) if safe_trans else ""

        # Hiển thị theo toggle
        display_html = ""
        if self.show_original_toggle.isChecked():
            display_html += f"<div class='content'>{html_text}</div>"
        if self.show_translated_toggle.isChecked() and html_trans:
            display_html += f"<div class='translated'>{html_trans}</div>"

        entry = (
            f"<div class='msg {'mention' if css_class=='mention' else ''}'>"
            f"<div class='timestamp'>[{html_lib.escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}]</div>"
            f"<div><span class='sender'>{html_lib.escape(sender)}</span> "
            f"in <span class='channel'>{html_lib.escape(channel)}</span></div>"
            f"{display_html}"
            f"</div>\n"
        )

        self.gui_body += entry
        self.set_web_html()
        append_html(sender, channel, message, css_class=("mention" if css_class=="mention" else "normal"), translated=translated)

    # ===================== SIGNAL HANDLERS =====================
    def _show_and_scroll_bottom(self):
        try:
            self.setWindowState(self.windowState() & ~Qt.WindowType.WindowMinimized)
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self.show()
            self.raise_()
            self.activateWindow()
            QTimer.singleShot(600, self._clear_on_top_flag)

            js = r"""
            (function(){
                var cont = document.querySelector('.container');
                if (cont) {
                    try { cont.scrollTop = cont.scrollHeight; } catch(e){}
                    try { if (cont.lastElementChild) cont.lastElementChild.scrollIntoView({behavior:'instant', block:'end'}); } catch(e){}
                } else {
                    try { window.scrollTo(0, document.body.scrollHeight); } catch(e){}
                }
                return true;
            })();
            """
            self.web.page().runJavaScript(js)
        except Exception:
            pass

    def _clear_on_top_flag(self):
        try:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
            self.show()
        except Exception:
            pass

    def on_set_connected(self, ok: bool):
        if ok:
            self.lbl_status.setText("Connected")
            self.lbl_status.setStyleSheet("color:#2563eb;")  # blue
        else:
            self.lbl_status.setText("Not connected")
            self.lbl_status.setStyleSheet("color:#b00020;")  # red

    def on_update_count(self, count: int):
        self.lbl_count.setText(f"Total messages: {count}")
