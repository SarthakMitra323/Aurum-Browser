import json
from PySide6.QtCore import QObject, Slot, Signal

class BrowserBridge(QObject):
    state_changed = Signal(str)
    tab_title_changed = Signal(str, str)
    tab_url_changed = Signal(str, str)
    tab_favicon_changed = Signal(str, str)
    active_tab_changed = Signal(str, str)
    focus_address = Signal()
    
    # Internal trigger for the sidebar
    sidebar_toggled = Signal()

    def __init__(self, engine):
        super().__init__()
        self.engine = engine 

    @Slot()
    def request_state(self):
        self.emit_state()

    @Slot(str)
    def navigate(self, query: str):
        self.engine.navigate_active_tab(query)

    @Slot()
    def new_tab(self):
        self.engine.create_tab()

    @Slot(str)
    def close_tab(self, tab_id: str):
        self.engine.close_tab(tab_id)

    @Slot(str)
    def switch_tab(self, tab_id: str):
        self.engine.switch_tab(tab_id)

    @Slot(int, int)
    def reorder_tabs(self, old_index: int, new_index: int):
        self.engine.reorder_tabs(old_index, new_index)

    @Slot()
    def go_back(self):
        self.engine.active_tab_action("back")

    @Slot()
    def go_forward(self):
        self.engine.active_tab_action("forward")

    @Slot()
    def reload(self):
        self.engine.active_tab_action("reload")

    @Slot()
    def toggle_guest_mode(self):
        self.engine.toggle_guest_mode()

    @Slot()
    def open_settings(self):
        self.engine.open_internal_page("settings")
        
    @Slot()
    def toggle_sidebar(self):
        self.sidebar_toggled.emit()

    def emit_state(self):
        try:
            if getattr(self, "engine", None) is None: return
                
            state = {
                "tabs": [
                    {
                        "id": tab.tab_id,
                        "title": tab.title,
                        "url": tab.url,
                        "favicon": tab.favicon
                    } for tab in self.engine.tabs
                ],
                "active_tab_id": self.engine.active_tab_id,
                "is_guest_mode": self.engine.is_guest_mode
            }
            self.state_changed.emit(json.dumps(state))
        except Exception as e:
            print(f"[Backend Error] Failed to emit state: {e}")