# notifications.py
import os
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from signals_bus import signals

tray_icon = None

def init_qt_tray(app):
    """Khởi tạo system tray với icon.png"""
    global tray_icon
    icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
    tray_icon = QSystemTrayIcon(QIcon(icon_path), parent=app)

    # Tạo menu cho tray
    menu = QMenu()
    quit_action = QAction("Thoát", tray_icon)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)
    tray_icon.setContextMenu(menu)

    # Hiển thị icon tray
    tray_icon.show()

    # Xử lý click vào tray icon
    def _on_activated(reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.Context):
            signals.clicked.emit()

    tray_icon.activated.connect(_on_activated)

    # Xử lý click vào thông báo
    tray_icon.messageClicked.connect(lambda: signals.clicked.emit())

def send_clickable_toast(title: str, message: str):
    """Hiện notification có thể click được"""
    if tray_icon:
        tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information)
