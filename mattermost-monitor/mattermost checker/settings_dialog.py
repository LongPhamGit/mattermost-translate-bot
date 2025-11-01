# settings_dialog.py
import json
import os
import requests
import urllib3

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QDialogButtonBox, QCheckBox,
    QWidget, QHBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt

from signals_bus import signals

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---- Load config from config_loader (if available) ----
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

# Path to config.json
if _HAVE_CFG_FILE and _CFG_FILE:
    CONFIG_FILE = _CFG_FILE
else:
    CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

HEADERS = {
    "Authorization": f"Bearer {MMAUTHTOKEN}" if MMAUTHTOKEN else "",
    "Content-Type": "application/json",
}
if MMUSERID:
    HEADERS["X-User-Id"] = MMUSERID


# -------- Helpers for reading/writing config.json --------
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


# -------- Mattermost API --------
def fetch_teams():
    if not SERVER_URL or not MMAUTHTOKEN:
        raise RuntimeError("SERVER_URL/MMAUTHTOKEN not configured.")
    url = f"{SERVER_URL}/api/v4/users/me/teams"
    resp = requests.get(url, headers=HEADERS, verify=False)
    resp.raise_for_status()
    return resp.json()

def fetch_channels(team_id):
    url = f"{SERVER_URL}/api/v4/users/me/teams/{team_id}/channels"
    resp = requests.get(url, headers=HEADERS, verify=False)
    resp.raise_for_status()
    return resp.json()


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Channel Settings")
        self.resize(800, 520)

        layout = QVBoxLayout(self)

        # Channel table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Watch", "Channel Name", "Channel ID"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 70)    # checkbox
        self.table.setColumnWidth(1, 420)   # channel name
        self.table.setColumnWidth(2, 280)   # channel id

        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.table)

        # OK / Cancel buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(self.button_box)
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)

        # Load channel data
        self._load_channels()

    def _load_channels(self):
        """Load channel list from all teams.
           Channels already in WATCH_CHANNELS will be pre-checked."""
        self.channels = []   # each item: dict channel + _team_name
        self.table.setRowCount(0)

        cfg = _read_config()
        current_watch = set(cfg.get("WATCH_CHANNELS", WATCH_CHANNELS or []))

        try:
            teams = fetch_teams()
        except Exception as e:
            QMessageBox.critical(self, "Load error", f"Could not fetch teams/channels:\n{e}")
            return

        team_name_by_id = {t.get("id"): t.get("display_name") for t in teams}

        for ch_team in teams:
            team_id = ch_team.get("id")
            try:
                channels = fetch_channels(team_id)
            except Exception as e:
                print("⚠️ fetch_channels error:", e)
                channels = []

            for ch in channels:
                row = self.table.rowCount()
                self.table.insertRow(row)

                # Column 1: checkbox
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

                # Column 2: Channel Name (fallback: display_name -> name -> "(no name)")
                ch_name = ch.get("display_name") or ch.get("name") or "(no name)"
                self.table.setItem(row, 1, QTableWidgetItem(ch_name))

                # Column 3: Channel ID
                self.table.setItem(row, 2, QTableWidgetItem(ch.get("id", "")))

                ch_copy = dict(ch)
                ch_copy["_team_name"] = team_name_by_id.get(ch.get("team_id"), "")
                self.channels.append(ch_copy)

    def _on_accept(self):
        """Save checked channels into config.json and notify WSClient."""
        selected_ids = []
        selected_comments = {}

        for row, ch in enumerate(self.channels):
            cb_widget = self.table.cellWidget(row, 0)
            if not cb_widget:
                continue
            cb = cb_widget.findChild(QCheckBox)
            if cb and cb.isChecked():
                ch_id = ch.get("id", "")
                ch_name = ch.get("display_name") or ch.get("name") or "(no name)"
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

        # Emit signal so WSClient applies immediately
        try:
            signals.watch_channels_changed.emit(selected_ids)
        except Exception:
            pass

        QMessageBox.information(self, "Saved", "Watch channels updated and applied immediately.")
        self.accept()
