from __future__ import annotations

from pathlib import Path

import pytest
from PySide6 import QtCore, QtGui

from pymodoro.app_ui import AppWindow
from pymodoro.app_ui_widgets.pages import Page
from pymodoro.settings import AppSettings, CheckInSettings, TimersSettings


@pytest.fixture
def settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        timers=TimersSettings(work_duration=10, break_duration=5, snooze_duration=3),
        check_in=CheckInSettings(prompts=["One", "Two"]),
        settings_path=tmp_path / "settings.yaml",
        metrics_log_path=tmp_path / "metrics.jsonl",
    )


def _current_sidebar_text(window: AppWindow) -> str:
    sidebar = window._sidebar  # type: ignore[attr-defined]
    current_item = sidebar._nav_item.currentItem()  # type: ignore[attr-defined]
    assert current_item is not None
    return current_item.text()


def _current_main_page(window: AppWindow) -> Page:
    main_area = window._main_area  # type: ignore[attr-defined]
    stack = main_area._stack  # type: ignore[attr-defined]
    current_widget = stack.currentWidget()
    for page, widget in main_area._page_widgets.items():  # type: ignore[attr-defined]
        if widget is current_widget:
            return page
    raise AssertionError("Current widget not found in page widgets")


def test_initial_state_dashboard_selected_and_visible(
    qcoreapp: QtCore.QCoreApplication, settings: AppSettings
) -> None:
    window = AppWindow(settings)

    assert _current_sidebar_text(window) == Page.DASHBOARD.value
    assert _current_main_page(window) is Page.DASHBOARD


def test_sidebar_click_selects_page_and_updates_main_area(
    qcoreapp: QtCore.QCoreApplication, settings: AppSettings
) -> None:
    window = AppWindow(settings)
    sidebar = window._sidebar  # type: ignore[attr-defined]

    items = sidebar._nav_item.findItems(  # type: ignore[attr-defined]
        Page.SETTINGS.value,
        QtCore.Qt.MatchFlag.MatchExactly,
    )
    assert items
    item = items[0]

    sidebar._nav_item.setCurrentItem(item)  # type: ignore[attr-defined]
    sidebar._nav_item.itemClicked.emit(item)  # type: ignore[attr-defined]

    assert _current_sidebar_text(window) == Page.SETTINGS.value
    assert _current_main_page(window) is Page.SETTINGS


def test_logo_click_shows_dashboard_and_updates_selection(
    qcoreapp: QtCore.QCoreApplication, settings: AppSettings
) -> None:
    window = AppWindow(settings)
    window.navigate_to_page(Page.SETTINGS)

    sidebar = window._sidebar  # type: ignore[attr-defined]
    sidebar._logo.clicked.emit()  # type: ignore[attr-defined]

    assert _current_sidebar_text(window) == Page.DASHBOARD.value
    assert _current_main_page(window) is Page.DASHBOARD


def test_navigate_to_dashboard_updates_sidebar_and_main_area(
    qcoreapp: QtCore.QCoreApplication, settings: AppSettings
) -> None:
    window = AppWindow(settings)
    window.navigate_to_page(Page.SETTINGS)

    window.navigate_to_page(Page.DASHBOARD)

    assert _current_sidebar_text(window) == Page.DASHBOARD.value
    assert _current_main_page(window) is Page.DASHBOARD


def test_navigate_to_settings_updates_sidebar_and_main_area(
    qcoreapp: QtCore.QCoreApplication, settings: AppSettings
) -> None:
    window = AppWindow(settings)

    window.navigate_to_page(Page.SETTINGS)

    assert _current_sidebar_text(window) == Page.SETTINGS.value
    assert _current_main_page(window) is Page.SETTINGS


def test_close_event_always_accepts(
    qcoreapp: QtCore.QCoreApplication,
    settings: AppSettings,
) -> None:
    window = AppWindow(settings)

    event = QtGui.QCloseEvent()
    window.closeEvent(event)

    assert event.isAccepted()
