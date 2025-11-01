from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl

class ExternalLinkPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, isMainFrame):
        if nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            if url.scheme() in ("http", "https", "mailto"):
                QDesktopServices.openUrl(url)
                return False
        return super().acceptNavigationRequest(url, nav_type, isMainFrame)

    def createWindow(self, web_window_type):
        temp_page = QWebEnginePage(self.profile())
        def _open_external(u: QUrl):
            if u.isValid() and u.scheme() in ("http", "https", "mailto"):
                QDesktopServices.openUrl(u)
        temp_page.urlChanged.connect(_open_external)
        return temp_page
