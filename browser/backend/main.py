import sys
import os
from PySide6.QtCore import QUrl, Qt, QFile, QIODevice, QTextStream, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QSplitter
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel

from bridge import BrowserBridge
from engine import BrowserEngine

class UICustomPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, msg, line, sourceID):
        if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            print(f"[Frontend JS Error] {sourceID}:{line}: {msg}")

class BrowserApplication(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aurum Browser")
        self.resize(1200, 800)
        
        # --- ENSURED EXACT LOGO LOOKUP MATCH ---
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            icon_base = getattr(sys, "_MEIPASS")
        else:
            icon_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            
        icon_path = os.path.join(icon_base, "logo.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        self.ui_view = QWebEngineView()
        self.ui_view.setMinimumWidth(260)
        self.tab_container = QStackedWidget()
        
        self.setup_bridge()
        
        self.splitter.addWidget(self.ui_view)
        self.splitter.addWidget(self.tab_container)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        layout.addWidget(self.splitter)

        self.setup_shortcuts()
        self.bridge.sidebar_toggled.connect(self.toggle_sidebar_visibility)

    def toggle_sidebar_visibility(self):
        if self.ui_view.isVisible():
            self.ui_view.hide()
        else:
            self.ui_view.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.ui_view.setMaximumWidth(int(self.width() * 0.5))

    def setup_bridge(self):
        ui_page = UICustomPage(self.ui_view)
        ui_page.setBackgroundColor(Qt.GlobalColor.white)
        self.ui_view.setPage(ui_page)
        self.ui_channel = QWebChannel()
        self.bridge = BrowserBridge(None)
        self.ui_channel.registerObject("bridge", self.bridge)
        ui_page.setWebChannel(self.ui_channel)

        self.engine = BrowserEngine(self.tab_container, self.bridge)
        setattr(self.bridge, "engine", self.engine)

        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_dir = getattr(sys, "_MEIPASS")
        else:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        ui_path = os.path.join(base_dir, "frontend", "index.html")
        channel_file = QFile(":/qtwebchannel/qwebchannel.js")
        channel_source = ""
        if channel_file.open(QIODevice.OpenModeFlag.ReadOnly):
            channel_source = QTextStream(channel_file).readAll()
            channel_file.close()
        try:
            with open(ui_path, "r", encoding="utf-8") as file:
                html_content = file.read()
            if channel_source:
                html_content = html_content.replace("</head>", f"<script>\n{channel_source}\n</script>\n</head>")
            self.ui_view.setHtml(html_content, QUrl.fromLocalFile(ui_path))
            QTimer.singleShot(0, self.engine.create_tab)
        except OSError as error:
            print(f"Failed to load UI: {error}")

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+L"), self, self.bridge.focus_address.emit)
        QShortcut(QKeySequence("Ctrl+T"), self, self.engine.create_tab)
        QShortcut(QKeySequence("Ctrl+W"), self, lambda: self.engine.close_tab(self.engine.active_tab_id)) # type: ignore
        QShortcut(QKeySequence("Ctrl+B"), self, self.toggle_sidebar_visibility)
        QShortcut(QKeySequence("Alt+Left"), self, lambda: self.engine.active_tab_action("back"))
        QShortcut(QKeySequence("Alt+Right"), self, lambda: self.engine.active_tab_action("forward"))
        QShortcut(QKeySequence("F5"), self, lambda: self.engine.active_tab_action("reload"))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = BrowserApplication()
    window.show()
    sys.exit(app.exec())