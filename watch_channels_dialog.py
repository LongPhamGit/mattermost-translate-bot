# watch_channels_dialog.py
import json
import os
import requests
import urllib3

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QHeaderView, QTableWidgetItem,
    QAbstractItemView, QWidget, QHBoxLayout, QCheckBox, QMessageBox, QDialogButtonBox
)
from PyQt6.QtCore import Qt
from signals_bus import signals

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from config_loader import SERVER_URL, MMAUTHTOKEN, MMUSERID, WATCH_CHANNELS, CONFIG_FILE as _CFG_FILE
    _HAVE_CFG_FILE = True
except Exception:
    SERVER_URL = ""
    MMAUTHTOKEN = ""
    MMUSERID = ""
    WATCH_CHANNELS = []
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

def _build_headers():
    headers = {"Content-Type": "application/json"}
    cfg = _read_config()
    token = cfg.get("MMAUTHTOKEN", MMAUTHTOKEN or "")
    uid   = cfg.get("MMUSERID", MMUSERID or "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if uid:
        headers["X-User-Id"] = uid
    return headers

def fetch_teams():
    cfg = _read_config()
    base = cfg.get("SERVER_URL", SERVER_URL or "")
    if not base:
        raise RuntimeError("SERVER_URL not set.")
    headers = _build_headers()
    if "Authorization" not in headers:
        raise RuntimeError("MMAUTHTOKEN not set.")
    resp = requests.get(f"{base}/api/v4/users/me/teams", headers=headers, verify=False)
    resp.raise_for_status()
    return resp.json(), base, headers

def fetch_channels(team_id, base, headers):
    resp = requests.get(f"{base}/api/v4/users/me/teams/{team_id}/channels", headers=headers, verify=False)
    resp.raise_for_status()
    return resp.json()

class WatchChannelsDialog(QDialog):
    """Chỉ chọn WATCH_CHANNELS."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Watch Channels")
        self.resize(880, 540)

        self.v = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Watch", "Channel Name", "Channel ID"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.v.addWidget(self.table)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.v.addWidget(self.button_box)
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)

        self._load_channels()

    def _load_channels(self):
        self.channels = []
        self.table.setRowCount(0)

        cfg = _read_config()
        current_watch = set(cfg.get("WATCH_CHANNELS", WATCH_CHANNELS or []))

        try:
            teams, base, headers = fetch_teams()
        except Exception as e:
            QMessageBox.critical(self, "Load error",
                                 f"Không thể tải team/channel.\nHãy vào Connection Settings trước.\n\n{e}")
            return

        team_name_by_id = {t.get("id"): t.get("display_name") for t in teams}
        for team in teams:
            team_id = team.get("id")
            try:
                channels = fetch_channels(team_id, base, headers)
            except Exception as e:
                print("⚠️ fetch_channels error:", e)
                channels = []

            for ch in channels:
                display_name = (ch.get("display_name") or "").strip()
                if not display_name:
                    continue
                row = self.table.rowCount()
                self.table.insertRow(row)

                cb_widget = QWidget()
                cb_layout = QHBoxLayout(cb_widget)
                cb_layout.setContentsMargins(0, 0, 0, 0)
                cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cb = QCheckBox()
                if ch.get("id") in current_watch:
                    cb.setChecked(True)
                cb_layout.addWidget(cb)
                cb_widget.setLayout(cb_layout)
                self.table.setCellWidget(row, 0, cb_widget)

                self.table.setItem(row, 1, QTableWidgetItem(display_name))
                self.table.setItem(row, 2, QTableWidgetItem(ch.get("id", "")))

                ch_copy = dict(ch)
                ch_copy["_team_name"] = team_name_by_id.get(ch.get("team_id"), "")
                self.channels.append(ch_copy)

    def _on_accept(self):
        selected_ids = []
        selected_comments = {}

        for row, ch in enumerate(self.channels):
            cb_widget = self.table.cellWidget(row, 0)
            if not cb_widget:
                continue
            cb = cb_widget.findChild(QCheckBox)
            if cb and cb.isChecked():
                ch_id = ch.get("id", "")
                ch_name = (ch.get("display_name") or "").strip()
                team_name = ch.get("_team_name", "")
                if ch_id:
                    selected_ids.append(ch_id)
                    selected_comments[ch_id] = f"{team_name} / {ch_name}" if team_name else ch_name

        cfg = _read_config()
        cfg["WATCH_CHANNELS"] = selected_ids
        cfg["_comment"] = selected_comments

        try:
            _write_config(cfg)
        except Exception as e:
            QMessageBox.critical(self, "Save error", f"Could not save config:\n{e}")
            return

        try:
            signals.watch_channels_changed.emit(selected_ids)
        except Exception:
            pass

        QMessageBox.information(self, "Saved", "Watch channels updated and applied.")
        self.accept()
