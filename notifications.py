# notifications.py
import os
import sys
import time
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from signals_bus import signals

# ====== App identity (Windows) ======
APP_AUMID = "LP.MattermostChecker"  # Phải khớp với SetCurrentProcessExplicitAppUserModelID

# ====== WinRT toast (Windows) - optional ======
_USE_WINRT = False
try:
    if sys.platform == "win32":
        from winrt.windows.data.xml.dom import XmlDocument
        from winrt.windows.ui.notifications import (
            ToastNotificationManager,
            ToastNotification,
        )
        _USE_WINRT = True
except Exception:
    _USE_WINRT = False

tray_icon = None

# ====== Guards / state ======
_initialized = False
_emit_in_progress = False

# Suppress ngắn sau click để chặn replay / burst
_SUPPRESS_TOAST_UNTIL = 0.0
_SUPPRESS_WINDOW_SEC = 1.5  # tăng/giảm theo thực tế

# Dedupe theo title trong 3s (chặn spam cùng nguồn)
_last_toast_by_title = {}  # {title: last_monotonic_time}
_DEDUP_WINDOW_SEC = 3.0

# Gate cứng cho QSystemTrayIcon (macOS/Linux): chỉ 1 toast/8s lọt tới OS
_TOAST_MIN_GAP_SEC = 8.0
_toast_cooldown_until = 0.0

# Tag/Group cố định cho WinRT để replace (singleton)
_WINRT_TAG = "main"
_WINRT_GROUP = "app"


# ---------- Windows helpers ----------
def _clear_windows_action_center():
    """Xoá toàn bộ toast của app khỏi Action Center (Windows 10+). Best-effort."""
    if not _USE_WINRT:
        return
    try:
        # Một số bản winrt có History / history
        history = getattr(ToastNotificationManager, "History", None) or getattr(
            ToastNotificationManager, "history", None
        )
        if history and hasattr(history, "clear"):
            history.clear(APP_AUMID)
    except Exception:
        pass


def _winrt_show_singleton_toast(title: str, message: str):
    """Hiển thị WinRT toast dùng Tag/Group để REPLACE (không xếp hàng)."""
    # Tạo XML ToastGeneric đơn giản
    xml = f"""
    <toast activationType="foreground">
      <visual>
        <binding template="ToastGeneric">
          <text>{title}</text>
          <text>{message}</text>
        </binding>
      </visual>
    </toast>
    """.strip()

    doc = XmlDocument()
    doc.load_xml(xml)
    toast = ToastNotification(doc)

    # Đặt tag/group để lần sau replace
    try:
        toast.tag = _WINRT_TAG
        toast.group = _WINRT_GROUP
    except Exception:
        # Một số binding có thể không expose attr; ignore
        pass

    # Trước khi show, cố gắng remove cái cũ (đảm bảo singleton)
    try:
        history = getattr(ToastNotificationManager, "History", None) or getattr(
            ToastNotificationManager, "history", None
        )
        if history and hasattr(history, "remove"):
            try:
                history.remove(_WINRT_TAG, _WINRT_GROUP, APP_AUMID)
            except Exception:
                pass
    except Exception:
        pass

    notifier = ToastNotificationManager.create_toast_notifier(APP_AUMID)
    notifier.show(toast)


# ---------- Common click handling ----------
def _emit_clicked_once():
    """Khi người dùng click toast/tray: suppress + clear Windows AC + emit clicked."""
    global _emit_in_progress, _SUPPRESS_TOAST_UNTIL
    if _emit_in_progress:
        return
    _emit_in_progress = True
    try:
        # Clear Action Center (nếu có WinRT), tránh “thẻ kế tiếp” bật lên
        _clear_windows_action_center()
        # Bật suppress ngắn để chặn burst
        _SUPPRESS_TOAST_UNTIL = time.monotonic() + _SUPPRESS_WINDOW_SEC
        # Cho app bring-to-front
        signals.clicked.emit()
    finally:
        QTimer.singleShot(0, _reset_emit_flag)


def _reset_emit_flag():
    global _emit_in_progress
    _emit_in_progress = False


# ---------- Public API ----------
def init_qt_tray(app):
    """Khởi tạo system tray (icon + menu). BẮT BUỘC gọi đúng 1 lần."""
    global tray_icon, _initialized
    if _initialized:
        return
    _initialized = True

    icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
    tray_icon = QSystemTrayIcon(QIcon(icon_path), parent=app)

    # Menu nhỏ
    menu = QMenu()
    quit_action = QAction("Close", tray_icon)
    quit_action.triggered.connect(app.quit, type=Qt.ConnectionType.UniqueConnection)
    menu.addAction(quit_action)
    tray_icon.setContextMenu(menu)

    tray_icon.show()

    # Click vào tray icon: chỉ Trigger/DoubleClick (không bắt Context/right-click)
    def _on_activated(reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            _emit_clicked_once()

    tray_icon.activated.connect(_on_activated, type=Qt.ConnectionType.UniqueConnection)

    # Với QSystemTrayIcon, click vào toast sẽ bắn messageClicked (Win/Mac/Linux)
    # Lưu ý: nếu dùng WinRT toast, click không đi qua đây (OS sẽ launch/activate app).
    tray_icon.messageClicked.connect(_emit_clicked_once, type=Qt.ConnectionType.UniqueConnection)


def send_clickable_toast(title: str, message: str):
    """
    Hiện thông báo:
      - Windows + winrt có sẵn: dùng WinRT toast “singleton” (replace).
      - Khác (hoặc thiếu winrt): dùng QSystemTrayIcon.showMessage với gate cứng.
    Bao gồm:
      - suppress sau click
      - dedupe theo title trong cửa sổ ngắn
      - lọc loại click ở init
    """
    if not tray_icon:
        return

    now = time.monotonic()

    # 1) Suppress ngay sau khi user click để tránh burst
    if now < _SUPPRESS_TOAST_UNTIL:
        return

    # 2) Dedupe theo title trong 3s
    last = _last_toast_by_title.get(title, 0.0)
    if (now - last) < _DEDUP_WINDOW_SEC:
        return

    # 3) Gửi
    if _USE_WINRT and sys.platform == "win32":
        # WinRT path: replace → không xếp hàng
        _winrt_show_singleton_toast(title, message)
        _last_toast_by_title[title] = now
        # (Không cần cooldown vì WinRT replace sẽ đè)
        return

    # Fallback: QSystemTrayIcon path
    global _toast_cooldown_until
    if now < _toast_cooldown_until:
        # Gate cứng: drop luôn (không defer) để tránh OS xếp hàng
        return

    tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information)
    _last_toast_by_title[title] = now
    _toast_cooldown_until = now + _TOAST_MIN_GAP_SEC
