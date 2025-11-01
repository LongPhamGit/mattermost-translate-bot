# connect_settings.py
import json
import os
import requests
import urllib3

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QWidget, QFormLayout, QLabel, QLineEdit,
    QHBoxLayout, QPushButton, QMessageBox, QDialogButtonBox
)
from PyQt6.QtCore import Qt

# Disable SSL warnings (self-signed)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---- Load config from config_loader (if available) ----
try:
    from config_loader import SERVER_URL, MMAUTHTOKEN, MMUSERID, CONFIG_FILE as _CFG_FILE
    _HAVE_CFG_FILE = True
except Exception:
    SERVER_URL = ""
    MMAUTHTOKEN = ""
    MMUSERID = ""
    _CFG_FILE = None
    _HAVE_CFG_FILE = False

if _HAVE_CFG_FILE and _CFG_FILE:
    CONFIG_FILE = _CFG_FILE
else:
    CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

def _read_config() -> dict:
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _write_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

class ConnectSettingsDialog(QDialog):
    """Thiết lập SERVER_URL, MMUSERID, MMAUTHTOKEN, MY_USERNAME + Test connect."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connection Settings")
        self.resize(640, 280)

        layout = QVBoxLayout(self)

        cfg = _read_config()

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.ed_server = QLineEdit(cfg.get("SERVER_URL", SERVER_URL or ""))
        self.ed_userid = QLineEdit(cfg.get("MMUSERID", MMUSERID or ""))
        self.ed_token = QLineEdit(cfg.get("MMAUTHTOKEN", MMAUTHTOKEN or ""))
        self.ed_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.ed_username = QLineEdit(cfg.get("MY_USERNAME", cfg.get("MY_USERNAME", "")))

        form.addRow(QLabel("SERVER_URL:"), self.ed_server)
        form.addRow(QLabel("MMUSERID:"), self.ed_userid)
        form.addRow(QLabel("MMAUTHTOKEN:"), self.ed_token)
        form.addRow(QLabel("MY_USERNAME:"), self.ed_username)

        # Buttons line: Test connect (left) + OK/Cancel (right)
        line = QWidget()
        hl = QHBoxLayout(line)
        hl.setContentsMargins(0, 0, 0, 0)

        self.btn_test = QPushButton("Test connect")
        self.btn_test.clicked.connect(self._on_test_connect)
        hl.addWidget(self.btn_test)
        hl.addStretch(1)

        layout.addWidget(form_widget)
        layout.addWidget(line)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(self.button_box)
        self.button_box.accepted.connect(self._on_save)
        self.button_box.rejected.connect(self.reject)

    def _headers_from_inputs(self):
        token = (self.ed_token.text() or "").strip()
        uid = (self.ed_userid.text() or "").strip()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if uid:
            headers["X-User-Id"] = uid
        return headers

    def _on_test_connect(self):
        server = (self.ed_server.text() or "").strip().rstrip("/")
        headers = self._headers_from_inputs()

        if not server or "Authorization" not in headers:
            QMessageBox.warning(self, "Missing info", "Vui lòng nhập SERVER_URL và MMAUTHTOKEN.")
            return
        try:
            resp = requests.get(f"{server}/api/v4/users/me", headers=headers, verify=False)
            resp.raise_for_status()
            me = resp.json()
            QMessageBox.information(self, "Connected",
                                    f"✅ OK\nUser: {me.get('username','')} ({me.get('id','')})")
        except Exception as e:
            QMessageBox.critical(self, "Connection failed", f"Không kết nối được:\n{e}")

    def _on_save(self):
        cfg = _read_config()
        cfg["SERVER_URL"]  = (self.ed_server.text() or "").strip().rstrip("/")
        cfg["MMUSERID"]    = (self.ed_userid.text() or "").strip()
        cfg["MMAUTHTOKEN"] = (self.ed_token.text() or "").strip()
        cfg["MY_USERNAME"] = (self.ed_username.text() or "").strip()

        try:
            _write_config(cfg)
        except Exception as e:
            QMessageBox.critical(self, "Save error", f"Could not save config:\n{e}")
            return

        # cập nhật biến global để phần còn lại dùng ngay
        try:
            global SERVER_URL, MMAUTHTOKEN, MMUSERID
            SERVER_URL  = cfg["SERVER_URL"]
            MMAUTHTOKEN = cfg["MMAUTHTOKEN"]
            MMUSERID    = cfg["MMUSERID"]
        except Exception:
            pass

        QMessageBox.information(self, "Saved", "Connection config đã được lưu.")
        self.accept()
