# settings_choice.py
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QDialogButtonBox, QLabel

class SettingsChoiceDialog(QDialog):
    def __init__(self, connected: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Settings")
        self.resize(360, 160)
        self.chosen = None  # "connect" | "watch" | None

        v = QVBoxLayout(self)
        v.addWidget(QLabel("Bạn muốn mở màn hình nào?"))

        self.btn_connect = QPushButton("Connection Settings")
        self.btn_watch   = QPushButton("Watch Channels")
        self.btn_watch.setEnabled(bool(connected))  # disable nếu chưa connect

        self.btn_connect.clicked.connect(self._choose_connect)
        self.btn_watch.clicked.connect(self._choose_watch)

        v.addWidget(self.btn_connect)
        v.addWidget(self.btn_watch)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _choose_connect(self):
        self.chosen = "connect"
        self.accept()

    def _choose_watch(self):
        self.chosen = "watch"
        self.accept()
