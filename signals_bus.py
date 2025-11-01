# signals_bus.py
from PyQt6.QtCore import QObject, pyqtSignal

class Signals(QObject):
    # sender, channel, original_message, translated_message
    new_message = pyqtSignal(str, str, str, str)

    # connection status
    set_connected = pyqtSignal(bool)

    # unread / total messages counter
    update_count = pyqtSignal(int)

    # click on notification -> bring main window to front
    clicked = pyqtSignal()

    # reset counter to zero (from Clear button)
    reset_count = pyqtSignal()

    # NEW: language of translation changed ("vi" | "en" | "ja" | "id")
    translate_lang_changed = pyqtSignal(str)

    # NEW: apply WATCH_CHANNELS immediately without restart
    # emits a Python list[str] of channel IDs to watch
    watch_channels_changed = pyqtSignal(list)

signals = Signals()
