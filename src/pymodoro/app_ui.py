from loguru import logger
from PySide6 import QtCore, QtWidgets

from pymodoro.app_ui_widgets.dashboard import Dashboard
from pymodoro.app_ui_widgets.settings_panel import SettingsPanel
from pymodoro.app_ui_widgets.sidebar import Sidebar
from pymodoro.settings import AppSettings
from pymodoro.tray import get_app_icon


class MainArea(QtWidgets.QFrame):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self._stack = QtWidgets.QStackedWidget(self)
        self._dashboard = Dashboard(self)
        self._settings_panel = SettingsPanel(settings, self)
        self._stack.addWidget(self._dashboard)
        self._stack.addWidget(self._settings_panel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

        self.setStyleSheet("""
            MainArea {
                background-color: palette(alternate-base);
                border-radius: 10px;
                margin: 12px 0px 0px 0px;
            }
        """)

    def show_dashboard(self) -> None:
        if (
            self._settings_panel.has_unsaved_changes()
            and not self._settings_panel.prepare_leave()
        ):
            return
        self._stack.setCurrentWidget(self._dashboard)

    def show_settings(self) -> None:
        self._stack.setCurrentWidget(self._settings_panel)


class AppWindow(QtWidgets.QMainWindow):
    def __init__(
        self,
        settings: AppSettings,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._settings = settings

        self._qt_settings = QtCore.QSettings("Pymodoro", "App")
        self.restore_geometry()

        self.setWindowTitle("Pymodoro App")
        self.setWindowIcon(get_app_icon())
        self.setMinimumSize(800, 500)

        self._build_ui()

    # ---- UI construction -------------------------------------------------
    def _build_ui(self) -> None:
        container = QtWidgets.QWidget()
        root = QtWidgets.QHBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = Sidebar(container)
        self._sidebar.navigate.connect(self._on_sidebar_navigate)

        self._main_area = MainArea(self._settings, container)

        root.addWidget(self._sidebar)
        root.addWidget(self._main_area)

        self.setCentralWidget(container)

    def get_settings_panel(self) -> SettingsPanel:
        return self._main_area._settings_panel

    # ---- Event handlers ---------------------------------------------------
    def _on_sidebar_navigate(self, page: str) -> None:
        match page:
            case "dashboard":
                self._main_area.show_dashboard()
            case "settings":
                self._main_area.show_settings()
            case _:
                logger.error(f"Unknown page: {page}")
        logger.info(f"Navigating to {page}")

    # ---- State restoration ------------------------------------------------
    def restore_geometry(self):
        geometry = self._qt_settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(980, 640)

    def closeEvent(self, event):
        self._qt_settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)
