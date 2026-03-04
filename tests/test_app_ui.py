from __future__ import annotations

from pathlib import Path

import pytest
from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QMessageBox

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


def test_navigation_away_from_settings_ignores_unsaved_changes(
    qcoreapp: QtCore.QCoreApplication,
    settings: AppSettings,
) -> None:
    window = AppWindow(settings)
    window.navigate_to_page(Page.SETTINGS)

    # Even if settings are (hypothetically) unsaved, navigation away should proceed without blocking.
    window.navigate_to_page(Page.DASHBOARD)

    assert _current_sidebar_text(window) == Page.DASHBOARD.value
    assert _current_main_page(window) is Page.DASHBOARD


def _make_settings_dirty(window: AppWindow) -> None:
    """Change a setting so the panel has unsaved changes."""
    panel = window.get_settings_panel()
    panel._timers_group.work_duration.setValue(
        panel._timers_group.work_duration.value() + 1
    )


def test_prepare_leave_discard_resets_ui_and_dirty_flag(
    qcoreapp: QtCore.QCoreApplication,
    settings: AppSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discard from the unsaved dialog should reset UI to saved settings and clear dirty flag."""
    window = AppWindow(settings)
    window.navigate_to_page(Page.SETTINGS)
    panel = window.get_settings_panel()

    original_work = panel._timers_group.work_duration.value()
    panel._timers_group.work_duration.setValue(original_work + 5)
    assert panel.has_unsaved_changes()

    # Simulate user choosing "Discard" in the dialog.
    monkeypatch.setattr(
        panel,
        "_confirm_close_for_dirty_state",
        lambda: QMessageBox.StandardButton.Discard,
    )

    assert panel.prepare_leave() is True
    # Dirty flag cleared and UI reverted to the original value.
    assert not panel.has_unsaved_changes()
    assert panel._timers_group.work_duration.value() == original_work


# --- Scenario A: Switch tabs with unsaved settings ---


def test_scenario_a_switch_tabs_with_unsaved_settings_navigates_and_keeps_values(
    qcoreapp: QtCore.QCoreApplication,
    settings: AppSettings,
) -> None:
    """Open Settings, change a value, navigate to Dashboard, then back; no dialog, values kept."""
    window = AppWindow(settings)
    window.navigate_to_page(Page.SETTINGS)
    panel = window.get_settings_panel()
    new_work = 99
    panel._timers_group.work_duration.setValue(new_work)
    assert panel.has_unsaved_changes()

    window.navigate_to_page(Page.DASHBOARD)
    assert _current_main_page(window) is Page.DASHBOARD

    window.navigate_to_page(Page.SETTINGS)
    assert _current_main_page(window) is Page.SETTINGS
    assert panel._timers_group.work_duration.value() == new_work


# --- Scenario B: Close window with unsaved settings (on Settings tab) ---


def test_scenario_b_close_with_unsaved_on_settings_cancel_keeps_window_open(
    qcoreapp: QtCore.QCoreApplication,
    settings: AppSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Close from Settings with unsaved changes, user cancels → window stays open."""
    window = AppWindow(settings)
    window.navigate_to_page(Page.SETTINGS)
    _make_settings_dirty(window)
    panel = window.get_settings_panel()
    monkeypatch.setattr(panel, "prepare_leave", lambda: False)

    event = QtGui.QCloseEvent()
    window.closeEvent(event)

    assert not event.isAccepted()


def test_scenario_b_close_with_unsaved_on_settings_save_or_discard_closes(
    qcoreapp: QtCore.QCoreApplication,
    settings: AppSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Close from Settings with unsaved changes, user saves or discards → window closes."""
    window = AppWindow(settings)
    window.navigate_to_page(Page.SETTINGS)
    _make_settings_dirty(window)
    panel = window.get_settings_panel()
    monkeypatch.setattr(panel, "prepare_leave", lambda: True)

    event = QtGui.QCloseEvent()
    window.closeEvent(event)

    assert event.isAccepted()


# --- Scenario C: Close window with unsaved settings (from Dashboard) ---


def test_scenario_c_close_with_unsaved_from_dashboard_cancel_keeps_window_open(
    qcoreapp: QtCore.QCoreApplication,
    settings: AppSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Open Settings, make changes, go to Dashboard, close → cancel → window stays open."""
    window = AppWindow(settings)
    window.navigate_to_page(Page.SETTINGS)
    _make_settings_dirty(window)
    window.navigate_to_page(Page.DASHBOARD)
    assert _current_main_page(window) is Page.DASHBOARD

    panel = window.get_settings_panel()
    monkeypatch.setattr(panel, "prepare_leave", lambda: False)

    event = QtGui.QCloseEvent()
    window.closeEvent(event)

    assert not event.isAccepted()


def test_scenario_c_close_with_unsaved_from_dashboard_save_or_discard_closes(
    qcoreapp: QtCore.QCoreApplication,
    settings: AppSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Open Settings, make changes, go to Dashboard, close → save/discard → window closes."""
    window = AppWindow(settings)
    window.navigate_to_page(Page.SETTINGS)
    _make_settings_dirty(window)
    window.navigate_to_page(Page.DASHBOARD)

    panel = window.get_settings_panel()
    monkeypatch.setattr(panel, "prepare_leave", lambda: True)

    event = QtGui.QCloseEvent()
    window.closeEvent(event)

    assert event.isAccepted()


# --- Scenario D: Close window with no unsaved settings ---


def test_scenario_d_close_with_no_unsaved_settings_closes_immediately(
    qcoreapp: QtCore.QCoreApplication,
    settings: AppSettings,
) -> None:
    """No changes in Settings; close from any page → no dialog, window closes."""
    window = AppWindow(settings)
    window.navigate_to_page(Page.SETTINGS)
    assert not window.get_settings_panel().has_unsaved_changes()

    event = QtGui.QCloseEvent()
    window.closeEvent(event)

    assert event.isAccepted()


def test_scenario_d_close_from_dashboard_with_no_unsaved_closes_immediately(
    qcoreapp: QtCore.QCoreApplication,
    settings: AppSettings,
) -> None:
    """No changes; close from Dashboard → no dialog, window closes."""
    window = AppWindow(settings)
    window.navigate_to_page(Page.DASHBOARD)
    assert not window.get_settings_panel().has_unsaved_changes()

    event = QtGui.QCloseEvent()
    window.closeEvent(event)

    assert event.isAccepted()


# --- Scenario E: Close after save or reset ---


def test_scenario_e_close_after_save_closes_immediately(
    qcoreapp: QtCore.QCoreApplication,
    settings: AppSettings,
) -> None:
    """Make changes, save, then close → no dialog, window closes."""
    window = AppWindow(settings)
    window.navigate_to_page(Page.SETTINGS)
    _make_settings_dirty(window)
    window.get_settings_panel()._save_settings()
    assert not window.get_settings_panel().has_unsaved_changes()

    event = QtGui.QCloseEvent()
    window.closeEvent(event)

    assert event.isAccepted()


def test_scenario_e_close_after_reset_closes_immediately(
    qcoreapp: QtCore.QCoreApplication,
    settings: AppSettings,
) -> None:
    """Make changes, reset, then close → no dialog, window closes."""
    window = AppWindow(settings)
    window.navigate_to_page(Page.SETTINGS)
    _make_settings_dirty(window)
    window.get_settings_panel()._reset_settings()
    assert not window.get_settings_panel().has_unsaved_changes()

    event = QtGui.QCloseEvent()
    window.closeEvent(event)

    assert event.isAccepted()
