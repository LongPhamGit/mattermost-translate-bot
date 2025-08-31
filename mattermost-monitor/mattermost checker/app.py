import sys
import platform
from PyQt6.QtWidgets import QApplication
from main_window import MainWindow
from ws_client import WSClient
from notifications import init_qt_tray
from signals_bus import signals


def flash_taskbar(win):
    if platform.system() == "Windows":
        try:
            import ctypes
            import ctypes.wintypes

            hwnd = int(win.winId())

            class FLASHWINFO(ctypes.Structure):
                _fields_ = [
                    ('cbSize', ctypes.wintypes.UINT),
                    ('hwnd', ctypes.wintypes.HWND),
                    ('dwFlags', ctypes.wintypes.DWORD),
                    ('uCount', ctypes.wintypes.UINT),
                    ('dwTimeout', ctypes.wintypes.DWORD),
                ]

            FLASHW_ALL = 3
            FLASHW_TIMERNOFG = 12  # nháy khi chưa focus

            flash_info = FLASHWINFO(
                ctypes.sizeof(FLASHWINFO),
                hwnd,
                FLASHW_ALL | FLASHW_TIMERNOFG,
                0,  # 0 = nhấp nháy vô hạn
                0
            )
            ctypes.windll.user32.FlashWindowEx(ctypes.byref(flash_info))

        except Exception as e:
            print("Lỗi FlashWindowEx:", e)


def main():
    app = QApplication(sys.argv)
    init_qt_tray(app)

    win = MainWindow()

    def show_main_window():
        if win.isMinimized():
            win.showNormal()
        else:
            win.show()

        win.raise_()
        win.activateWindow()

    # --- Signal xử lý ---
    signals.clicked.connect(show_main_window)   # khi click notification/tray
    signals.new_message.connect(lambda _: flash_taskbar(win))  # khi có tin nhắn thì nhấp nháy taskbar

    # WebSocket client
    wsclient = WSClient()
    wsclient.start()

    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
