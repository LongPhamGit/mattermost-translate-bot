# MattermostChecker.py
import os, sys, platform
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from main_window import MainWindow
from ws_client import WSClient
from notifications import init_qt_tray
from signals_bus import signals

APP_ID = "LP.MattermostChecker"  # dùng cho AppUserModelID + tên IPC server + tên mutex

# --- AppUserModelID (Windows) để taskbar nhận đúng icon ---
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass

def resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)

# ---------- HARD SINGLE-INSTANCE (Windows mutex + IPC) ----------
_win_mutex = None

def _win_acquire_mutex(name: str) -> bool:
    """Tạo mutex đặt tên; trả về True nếu thành công (instance đầu tiên)."""
    if sys.platform != "win32":
        return True
    import ctypes
    from ctypes import wintypes
    CreateMutexW = ctypes.windll.kernel32.CreateMutexW
    GetLastError = ctypes.windll.kernel32.GetLastError
    ERROR_ALREADY_EXISTS = 183

    global _win_mutex
    _win_mutex = CreateMutexW(None, False, name)
    # _win_mutex có thể là handle (non-zero). Kiểm tra lỗi tồn tại.
    exists = (GetLastError() == ERROR_ALREADY_EXISTS)
    return not exists  # True nếu mutex chưa tồn tại (tức là instance đầu)

def _try_connect_existing(server_name: str) -> bool:
    """Thử kết nối tới instance đang chạy; nếu được thì gửi 'ACTIVATE' và báo là đã có instance."""
    sock = QLocalSocket()
    sock.connectToServer(server_name)
    if sock.waitForConnected(150):
        try:
            sock.write(b"ACTIVATE")
            sock.flush()
            sock.waitForBytesWritten(150)
        except Exception:
            pass
        finally:
            sock.disconnectFromServer()
        return True
    return False

def _create_primary_server(server_name: str) -> QLocalServer:
    """Tạo server làm 'khóa' single-instance cho instance chính."""
    QLocalServer.removeServer(server_name)
    server = QLocalServer()
    ok = server.listen(server_name)
    if not ok:
        QLocalServer.removeServer(server_name)
        if not server.listen(server_name):
            raise RuntimeError("Không thể tạo single-instance server.")
    return server
# ---------------------------------------------------------------

def flash_taskbar(win):
    if platform.system() == "Windows":
        try:
            import ctypes, ctypes.wintypes
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
            FLASHW_TIMERNOFG = 12
            flash_info = FLASHWINFO(
                ctypes.sizeof(FLASHWINFO),
                hwnd,
                FLASHW_ALL | FLASHW_TIMERNOFG,
                0,
                0
            )
            ctypes.windll.user32.FlashWindowEx(ctypes.byref(flash_info))
        except Exception as e:
            print("Lỗi FlashWindowEx:", e)

def main():
    # --- Nếu đã có instance đang chạy (IPC server tồn tại) → kích hoạt & thoát ---
    if _try_connect_existing(APP_ID):
        sys.exit(0)

    # --- Nếu là Windows: tạo mutex tên global; nếu đã có → kích hoạt & thoát ---
    #     (Trong một số trường hợp Action Center/OS vẫn launch exe: mutex sẽ chặn)
    if not _win_acquire_mutex(r"Global\\" + APP_ID):
        # Instance khác đã giữ mutex → gửi ACTIVATE qua IPC và thoát
        _try_connect_existing(APP_ID)
        sys.exit(0)

    app = QApplication(sys.argv)

    # Sau khi chắc chắn là instance đầu → mở IPC server để nhận ACTIVATE
    try:
        single_server = _create_primary_server(APP_ID)
    except Exception as e:
        print("Single-instance error:", e)
        single_server = None

    # --- Icon cho app ---
    app_icon = QIcon(resource_path("icon.ico"))
    app.setWindowIcon(app_icon)
    app.setQuitOnLastWindowClosed(False)

    # --- System tray ---
    init_qt_tray(app)

    # --- Main window (instance duy nhất) ---
    win = MainWindow()
    win.setWindowIcon(app_icon)

    def show_main_window():
        if win.isMinimized():
            win.showNormal()
        else:
            win.show()
        win.raise_()
        win.activateWindow()
        try:
            app.processEvents()
        except Exception:
            pass

    # Nhận ACTIVATE từ instance mới (nếu có)
    if single_server is not None:
        def _on_new_connection():
            # Hiển thị cửa sổ ngay khi nhận được kết nối để giảm độ trễ
            show_main_window()
            try:
                conn = single_server.nextPendingConnection()
            except Exception:
                conn = None

            if conn is not None:
                try:
                    # Đọc dữ liệu nếu có nhưng chỉ đợi trong thời gian rất ngắn
                    if not conn.bytesAvailable():
                        conn.waitForReadyRead(5)
                    if conn.bytesAvailable():
                        conn.readAll()
                except Exception:
                    pass
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    try:
                        conn.deleteLater()
                    except Exception:
                        pass

            try:
                flash_taskbar(win)
            except Exception:
                pass

        single_server.newConnection.connect(_on_new_connection, type=Qt.ConnectionType.UniqueConnection)

    # Kết nối tray/notification click -> bring-to-front
    signals.clicked.connect(show_main_window, type=Qt.ConnectionType.UniqueConnection)
    signals.new_message.connect(lambda *args: flash_taskbar(win), type=Qt.ConnectionType.UniqueConnection)

    # --- WebSocket client ---
    wsclient = WSClient()
    wsclient.start()

    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
