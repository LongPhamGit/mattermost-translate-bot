# main_window.py
import os
import html as html_lib
from datetime import datetime
from markdown import markdown

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, pyqtProperty
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QComboBox,
    QMessageBox, QSizePolicy, QGridLayout
)
from PyQt6.QtGui import QFont, QPainter, QBrush, QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView

from config_loader import HTML_LOG_FILE, MY_USERNAME
from signals_bus import signals
from html_log import HTML_HEADER, HTML_FOOTER, append_html
from webview_pages import ExternalLinkPage


# ===================== ToggleSwitch =====================
class ToggleSwitch(QPushButton):
    """Custom toggle switch with sliding thumb animation."""
    def __init__(self, parent=None, checked=True):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(56, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setChecked(checked)

        self._on_color = QColor("#2F3C56")   # navy
        self._off_color = QColor("#ADADBA")  # gray

        self._thumb_pos = self.width() - self.height() + 2 if checked else 2
        self._anim = QPropertyAnimation(self, b"thumbPos", self)
        self._anim.setDuration(180)

    def getThumbPos(self):
        return int(self._thumb_pos)

    def setThumbPos(self, pos):
        self._thumb_pos = int(pos)
        self.update()

    thumbPos = pyqtProperty(int, fget=getThumbPos, fset=setThumbPos)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg = self._on_color if self.isChecked() else self._off_color
        p.setBrush(QBrush(bg))
        p.setPen(Qt.PenStyle.NoPen)
        r = self.height() // 2
        p.drawRoundedRect(0, 0, self.width(), self.height(), r, r)

        d = self.height() - 4
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(self._thumb_pos, 2, d, d)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self.isChecked())
            self._animate_toggle()
            e.accept()
            return
        super().mousePressEvent(e)

    def _animate_toggle(self):
        left = 2
        right = self.width() - self.height() + 2
        start = self._thumb_pos
        end = right if self.isChecked() else left
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()


# ===================== LanguageCombo =====================
class LanguageCombo(QComboBox):
    """QComboBox that scrolls to current item when popup opens."""
    def showPopup(self):
        super().showPopup()
        idx = self.currentIndex()
        view = self.view()
        if idx >= 0:
            model_idx = self.model().index(idx, 0)
            view.setCurrentIndex(model_idx)
            view.scrollTo(model_idx)


# ===================== MainWindow =====================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mattermost Checker with Gemini Translate")

        # ===== Banner =====
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
            }
        """)

        font_btn = QFont("Arial", 12)
        font_label = QFont("Arial", 12)

        # Nút mở log và Settings
        self.btn_open = QPushButton("Open log file")
        self.btn_open.setFont(font_btn)
        self.btn_open.setStyleSheet("padding:5px 12px;")

        self.btn_settings = QPushButton("⚙ Settings")
        self.btn_settings.setFont(font_btn)
        self.btn_settings.setStyleSheet("padding:5px 12px;")
        self.btn_settings.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.lbl_status = QLabel("Not connected")
        self.lbl_status.setFont(font_label)
        self.lbl_status.setStyleSheet("color:#b00020;")

        self.lbl_count = QLabel("Total messages: 0")
        self.lbl_count.setFont(font_label)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setFont(font_btn)
        self.btn_clear.setStyleSheet("padding:5px 12px;")

        # ===== Controls card =====
        controls_card = QWidget()
        controls_card.setObjectName("controlsCard")
        controls_card.setStyleSheet("""
            #controlsCard {
                background: #f7f9fc;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
            }
        """)
        grid = QGridLayout(controls_card)
        grid.setContentsMargins(18, 12, 18, 12)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        self.show_original_toggle = ToggleSwitch(checked=True)
        self.show_translated_toggle = ToggleSwitch(checked=True)

        lbl_original = QLabel("Show Original Messages")
        lbl_translated = QLabel("Show Translated Messages")
        for l in (lbl_original, lbl_translated):
            l.setFont(QFont("Segoe UI", 12))
            l.setStyleSheet("color:#111827;")

        lbl_translate_to = QLabel("Translate to:")
        lbl_translate_to.setFont(QFont("Segoe UI", 11))
        lbl_translate_to.setStyleSheet("color:#6b7280;")

        self.lang_combo = LanguageCombo()
        self.lang_combo.addItems(["Vietnamese", "English", "Japanese", "Indonesian"])
        self.lang_combo.setCurrentText("Vietnamese")
        self.lang_combo.setMinimumWidth(240)
        self.lang_combo.setMaximumWidth(280)
        self.lang_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.lang_combo.setStyleSheet("""
            QComboBox {
                font: 12pt "Segoe UI";
                padding: 6px 10px;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                background: #ffffff;
                color: #111827;
            }
            QComboBox:hover { border-color: #9ca3af; }
            QComboBox::drop-down { width: 26px; border: 0px; }
            QComboBox QAbstractItemView {
                font: 12pt "Segoe UI";
                background: #ffffff;
                border: 1px solid #e5e7eb;
                selection-background-color: #e5e7eb;
                selection-color: #111827;
                outline: 0;
            }
        """)

        translate_group = QWidget()
        tl = QHBoxLayout(translate_group)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(8)
        tl.addWidget(lbl_translate_to)
        tl.addWidget(self.lang_combo)

        grid.addWidget(lbl_original,                0, 0, Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(self.show_original_toggle,   0, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(lbl_translated,              1, 0, Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(self.show_translated_toggle, 1, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(translate_group,             1, 3, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 0)

        # ===== Top bar =====
        left_layout = QHBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        left_layout.addWidget(self.btn_open)
        left_layout.addWidget(self.btn_settings)   # thêm nút Settings

        center_layout = QHBoxLayout()
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(4)
        center_layout.addWidget(self.lbl_status)

        right_layout = QHBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(self.lbl_count)
        right_layout.addWidget(self.btn_clear)

        bar_layout = QHBoxLayout()
        bar_layout.addLayout(left_layout)
        bar_layout.addStretch(1)
        bar_layout.addLayout(center_layout)
        bar_layout.addStretch(1)
        bar_layout.addLayout(right_layout)

        top_layout = QVBoxLayout()
        top_layout.setContentsMargins(2, 0, 2, 0)
        top_layout.setSpacing(8)
        top_layout.addLayout(bar_layout)
        top_layout.addWidget(controls_card)

        top_widget = QWidget()
        top_widget.setLayout(top_layout)
        top_widget.setFixedHeight(128)
        top_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # ===== Webview =====
        self.web = QWebEngineView()
        self.web.setPage(ExternalLinkPage(self.web))
        self.gui_body = ""
        try:
            self.web.loadFinished.disconnect()
        except Exception:
            pass
        self.web.loadFinished.connect(self._on_web_load_finished, type=Qt.ConnectionType.UniqueConnection)

        self.set_web_html()

        # ===== Footer =====
        footer = QLabel("© 2025 LongPham. All Rights Reserved. <2025/06/05 V1.5.0>")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setFont(QFont("Segoe UI", 9))
        footer.setStyleSheet("color:#6b7280; padding:2px;")
        footer.setFixedHeight(20)

        v = QVBoxLayout()
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(8)
        v.addWidget(banner)
        v.addWidget(top_widget)
        v.addWidget(self.web)
        v.addWidget(footer)
        self.setLayout(v)
        self.resize(1000, 780)

        # ===== Signals =====
        self.btn_open.clicked.connect(self.open_log, type=Qt.ConnectionType.UniqueConnection)
        self.btn_clear.clicked.connect(self.clear_display_and_reset_count, type=Qt.ConnectionType.UniqueConnection)
        self.btn_settings.clicked.connect(self.open_settings, type=Qt.ConnectionType.UniqueConnection)

        signals.new_message.connect(self.on_new_message, type=Qt.ConnectionType.UniqueConnection)
        signals.set_connected.connect(self.on_set_connected, type=Qt.ConnectionType.UniqueConnection)
        signals.update_count.connect(self.on_update_count, type=Qt.ConnectionType.UniqueConnection)
        signals.clicked.connect(self._show_and_scroll_bottom, type=Qt.ConnectionType.QueuedConnection)

        self.lang_combo.currentTextChanged.connect(self._emit_current_lang, type=Qt.ConnectionType.UniqueConnection)
        self._emit_current_lang()

    # ===================== Web content =====================
    def set_web_html(self):
        self.web.setHtml(HTML_HEADER + self.gui_body + HTML_FOOTER)
        QTimer.singleShot(0, lambda: self.web.page().runJavaScript(self._scroll_bottom_js()))

    def _scroll_bottom_js(self) -> str:
        return r"""
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

    def _on_web_load_finished(self, ok: bool):
        try:
            self.web.page().runJavaScript(self._scroll_bottom_js())
        except Exception:
            pass

    # ===================== Actions =====================
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

    def open_settings(self):
        from settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        dlg.exec()

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

        append_html(
            sender, channel, message,
            css_class=("mention" if css_class == "mention" else "normal"),
            translated=translated
        )

    # ===================== Bring to front =====================
    def _show_and_scroll_bottom(self):
        try:
            self.setWindowState(self.windowState() & ~Qt.WindowType.WindowMinimized)
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self.show()
            self.raise_()
            self.activateWindow()
            QTimer.singleShot(600, self._clear_on_top_flag)
            self.web.page().runJavaScript(self._scroll_bottom_js())
        except Exception:
            pass

    def _clear_on_top_flag(self):
        try:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
            self.show()
        except Exception:
            pass

    # ===================== Status & counter =====================
    def on_set_connected(self, ok: bool):
        if ok:
            self.lbl_status.setText("Connected")
            self.lbl_status.setStyleSheet("color:#2563eb;")
        else:
            self.lbl_status.setText("Not connected")
            self.lbl_status.setStyleSheet("color:#b00020;")

    def on_update_count(self, count: int):
        self.lbl_count.setText(f"Total messages: {count}")

    # ===================== Language broadcast =====================
    def _emit_current_lang(self):
        name = self.lang_combo.currentText()
        code = {
            "Vietnamese": "vi",
            "English":   "en",
            "Japanese":  "ja",
            "Indonesian":"id",
        }.get(name, "vi")
        try:
            signals.translate_lang_changed.emit(code)
        except Exception:
            pass
