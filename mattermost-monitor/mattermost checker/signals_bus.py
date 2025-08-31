from PyQt6.QtCore import QObject, pyqtSignal

class Signals(QObject):
    new_message = pyqtSignal(str, str, str, str)
    set_connected = pyqtSignal(bool)
    update_count = pyqtSignal(int)
    clicked = pyqtSignal()
    # NEW: reset bộ đếm tin nhắn về 0
    reset_count = pyqtSignal()

signals = Signals()
