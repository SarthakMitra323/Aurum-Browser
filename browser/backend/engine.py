import uuid
import os
import sys
import urllib.parse
from PySide6.QtCore import QUrl, QFileInfo, Qt, QTimer, QBuffer, QIODevice
from PySide6.QtWidgets import QStackedWidget, QFileDialog, QMessageBox
from PySide6.QtWebEngineCore import (QWebEngineProfile, QWebEnginePage,
                                     QWebEngineSettings, QWebEnginePermission,
                                     qWebEngineChromiumVersion)
from PySide6.QtWebEngineWidgets import QWebEngineView

class TabData:
    def __init__(self, view: QWebEngineView):
        self.tab_id = str(uuid.uuid4())
        self.view = view
        self.title = "New Tab"
        self.url = ""
        self.favicon = ""

class ContentInterceptorPage(QWebEnginePage):
    """
    Intercepts internal URLs from the frontend to trigger secure Python state changes.
    """
    def __init__(self, profile, parent, engine_ref):
        super().__init__(profile, parent)
        self.engine_ref = engine_ref
        self.permissionRequested.connect(engine_ref.handle_permission_request)

    def acceptNavigationRequest(self, url, _type, isMainFrame):
        # Only intercept main-frame requests to prevent subframes from triggering actions
        if isMainFrame and url.host() == "aurum.internal":
            parsed_url = urllib.parse.parse_qs(url.query())
            
            if url.path() == "/set-search":
                engine = parsed_url.get("engine", [""])[0]
                if engine in {"google", "duckduckgo"}:
                    self.engine_ref.search_engine = engine
            elif url.path() == "/navigate":
                raw_val = parsed_url.get("q", [""])[0]
                if raw_val:
                    # Defer navigation to safely escape the event loop
                    QTimer.singleShot(0, lambda: self.engine_ref.navigate_active_tab(raw_val))
            
            return False 
        return super().acceptNavigationRequest(url, _type, isMainFrame)


class BrowserEngine:
    def __init__(self, tab_container: QStackedWidget, bridge):
        self.tab_container = tab_container
        self.bridge = bridge
        
        self.tabs: list[TabData] = []
        self.active_tab_id = None
        self.is_guest_mode = False
        self.search_engine = "duckduckgo" 

        # Explicitly configure Named Profile for standard cache optimization
        self.persistent_profile = QWebEngineProfile("AurumBrowser", tab_container)
        self.persistent_profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
        )
        self._configure_profile(self.persistent_profile, disk_cache=True)
        self.persistent_profile.downloadRequested.connect(self.handle_download)

        # Explicitly configure Guest Profile as entirely off-the-record
        self.guest_profile = QWebEngineProfile() 
        self._configure_profile(self.guest_profile, disk_cache=False)
        self.guest_profile.downloadRequested.connect(self.handle_download)

    def get_current_profile(self):
        return self.guest_profile if self.is_guest_mode else self.persistent_profile

    @staticmethod
    def _configure_profile(profile: QWebEngineProfile, disk_cache: bool):
        settings = profile.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
        
        # Enables blazing fast back/forward navigation without re-downloading resources
        settings.setAttribute(QWebEngineSettings.WebAttribute.BackForwardCacheEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        
        # Dictates Disk vs Memory caching strategies depending on the profile mode
        cache_type = (QWebEngineProfile.HttpCacheType.DiskHttpCache 
                      if disk_cache else QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        profile.setHttpCacheType(cache_type)
        profile.setHttpUserAgent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{qWebEngineChromiumVersion()} "
            "Safari/537.36"
        )

    def create_tab(self, url: str = "about:blank"):
        view = QWebEngineView()
        page = ContentInterceptorPage(self.get_current_profile(), view, self)
        view.setPage(page)
        
        tab = TabData(view)
        
        view.titleChanged.connect(lambda t: self.update_tab_title(tab.tab_id, t))
        view.urlChanged.connect(lambda u: self.update_tab_url(tab.tab_id, u))
        view.iconChanged.connect(lambda icon: self.update_tab_icon(tab.tab_id, icon))
        view.loadStarted.connect(self.bridge.emit_state)
        view.loadFinished.connect(lambda ok: self.bridge.emit_state())
        view.renderProcessTerminated.connect(
            lambda status, code: print(f"[WebEngine Renderer] {status.name} ({code})")
        )

        self.tabs.append(tab)
        self.tab_container.addWidget(view)
        
        self.switch_tab(tab.tab_id)
        
        if url == "about:blank":
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                base_dir = getattr(sys, "_MEIPASS")
            else:
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            home_path = os.path.join(base_dir, "frontend", "home.html")
            view.setUrl(QUrl.fromLocalFile(home_path))
        else:
            view.setUrl(QUrl.fromUserInput(url))

    def close_tab(self, tab_id: str):
        if len(self.tabs) <= 1:
            self.create_tab()

        tab = self._get_tab(tab_id)
        if tab:
            self.tab_container.removeWidget(tab.view)
            tab.view.deleteLater()
            self.tabs.remove(tab)
            
            if self.active_tab_id == tab_id:
                self.switch_tab(self.tabs[-1].tab_id)
            else:
                self.bridge.emit_state()

    def switch_tab(self, tab_id: str):
        tab = self._get_tab(tab_id)
        if tab:
            self.active_tab_id = tab_id
            self.tab_container.setCurrentWidget(tab.view)
            self.bridge.active_tab_changed.emit(tab_id, tab.url if "home.html" not in tab.url and "settings.html" not in tab.url else "")
            self.bridge.emit_state()

    def reorder_tabs(self, old_index: int, new_index: int):
        if 0 <= old_index < len(self.tabs) and 0 <= new_index < len(self.tabs):
            tab = self.tabs.pop(old_index)
            self.tabs.insert(new_index, tab)
            self.bridge.emit_state()

    def navigate_active_tab(self, query: str):
        tab = self._get_tab(self.active_tab_id) # type: ignore
        if not tab: return
        
        query = query.strip()
        if not query: return
        
        # Check if query is likely a search string, else treat as URL
        if " " in query or not ("." in query or query.startswith(("http://", "https://", "about:", "file://"))):
            encoded_query = urllib.parse.quote_plus(query)
            if self.search_engine == "google":
                url = f"https://www.google.com/search?q={encoded_query}"
            else:
                url = f"https://duckduckgo.com/?q={encoded_query}"
        else:
            url = query

        # Using fromUserInput securely infers the protocol format (like adding http://)
        tab.view.setUrl(QUrl.fromUserInput(url))

    def active_tab_action(self, action: str):
        tab = self._get_tab(self.active_tab_id) # type: ignore
        if not tab: return
        
        if action == "back": tab.view.back()
        elif action == "forward": tab.view.forward()
        elif action == "reload": tab.view.reload()

    def toggle_guest_mode(self):
        self.is_guest_mode = not self.is_guest_mode
        for tab in list(self.tabs):
            self.close_tab(tab.tab_id)
        self.bridge.emit_state()

    def handle_download(self, download):
        default_path = os.path.expanduser(f"~/Downloads/{download.downloadFileName()}")
        path, _ = QFileDialog.getSaveFileName(self.tab_container, "Save File", default_path)
        
        if path:
            download.setDownloadDirectory(QFileInfo(path).path())
            download.setDownloadFileName(QFileInfo(path).fileName())
            download.accept()
        else:
            download.cancel()

    def handle_permission_request(self, permission: QWebEnginePermission):
        media_types = {
            QWebEnginePermission.PermissionType.MediaAudioCapture: "microphone",
            QWebEnginePermission.PermissionType.MediaVideoCapture: "camera",
            QWebEnginePermission.PermissionType.MediaAudioVideoCapture: "camera and microphone",
        }
        requested = media_types.get(permission.permissionType())
        if not requested:
            permission.deny()
            return

        origin = permission.origin().host() or permission.origin().toString()
        answer = QMessageBox.question(
            self.tab_container,
            "Permission request",
            f"Allow {origin} to use your {requested}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            permission.grant()
        else:
            permission.deny()

    def open_internal_page(self, page_type: str):
        if page_type == "settings":
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                base_dir = getattr(sys, "_MEIPASS")
            else:
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            
            settings_path = os.path.join(base_dir, "frontend", "settings.html")
            url = f"file:///{settings_path.replace(os.sep, '/')}?engine={self.search_engine}"
            self.create_tab(url)

    def _get_tab(self, tab_id: str):
        for tab in self.tabs:
            if tab.tab_id == tab_id:
                return tab
        return None

    def update_tab_title(self, tab_id: str, title: str):
        tab = self._get_tab(tab_id)
        if tab:
            display_title = title if "home.html" not in title else "New Tab"
            display_title = "Settings" if "settings.html" in tab.url else display_title
            tab.title = display_title
            self.bridge.tab_title_changed.emit(tab_id, display_title)

    def update_tab_url(self, tab_id: str, url: QUrl):
        tab = self._get_tab(tab_id)
        if tab:
            display_url = url.toString() if "home.html" not in url.toString() and "settings.html" not in url.toString() else ""
            tab.url = display_url
            self.bridge.tab_url_changed.emit(tab_id, display_url)

    def update_tab_icon(self, tab_id: str, icon):
        tab = self._get_tab(tab_id)
        if not tab or icon.isNull():
            return
        pixmap = icon.pixmap(16, 16)
        if pixmap.isNull():
            return
        image = pixmap.toImage()
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.ReadWrite)
        image.save(buffer, "PNG")
        tab.favicon = "data:image/png;base64," + buffer.data().toBase64().toStdString()
        self.bridge.tab_favicon_changed.emit(tab_id, tab.favicon)

    def get_active_url(self):
        tab = self._get_tab(self.active_tab_id) # type: ignore
        if not tab: return ""
        return tab.url if "home.html" not in tab.url and "settings.html" not in tab.url else ""