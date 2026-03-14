from typing import cast

from loguru import logger
from PySide6 import QtCore, QtGui, QtWidgets

from pymodoro.app_ui_widgets.calendar_page import CalendarPage
from pymodoro.app_ui_widgets.dashboard import Dashboard
from pymodoro.app_ui_widgets.pages import Page
from pymodoro.app_ui_widgets.settings_panel import SettingsPanel
from pymodoro.app_ui_widgets.sidebar import Sidebar
from pymodoro.settings import AppSettings
from pymodoro.tray import get_app_icon


class MainArea(QtWidgets.QFrame):
    def __init__(
        self, settings: AppSettings, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._page_widgets: dict[Page, QtWidgets.QWidget] = {
            Page.DASHBOARD: Dashboard(settings, self),
            Page.CALENDAR: CalendarPage(settings, self),
            Page.SETTINGS: SettingsPanel(settings, self),
        }

        self._stack = QtWidgets.QStackedWidget(self)
        [self._stack.addWidget(widget) for widget in self._page_widgets.values()]

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

    @property
    def settings_panel(self) -> SettingsPanel:
        return cast(SettingsPanel, self._page_widgets[Page.SETTINGS])

    def show_page(self, page: Page) -> None:
        self._stack.setCurrentWidget(self._page_widgets[page])


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
        self._sidebar.navigate.connect(self.navigate_to_page)

        self._main_area = MainArea(self._settings, container)

        root.addWidget(self._sidebar)
        root.addWidget(self._main_area)
        self.navigate_to_page(Page.DASHBOARD)

        self.setCentralWidget(container)

    def get_settings_panel(self) -> SettingsPanel:
        return cast(SettingsPanel, self._main_area._page_widgets[Page.SETTINGS])

    # ---- Navigation handlers ----------------------------------------------
    def navigate_to_page(self, page: Page) -> None:
        logger.info(f"Navigating to page: {page}")
        self._sidebar.set_current_page(page)
        self._main_area.show_page(page)

    # ---- State restoration ------------------------------------------------
    def restore_geometry(self) -> None:
        geometry = self._qt_settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(980, 640)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if not self._main_area.settings_panel.prepare_leave():
            return event.ignore()
        self._qt_settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)
