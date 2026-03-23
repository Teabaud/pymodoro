from __future__ import annotations

from typing import Any

from PySide6 import QtCore

from pymodoro.app_ui_widgets.pages import Page
from pymodoro.app_ui_widgets.sidebar import Sidebar


def test_sidebar_item_click_emits_correct_page(
    qcoreapp: QtCore.QCoreApplication,
) -> None:
    sidebar = Sidebar()
    received: list[Page] = []
    sidebar.navigate.connect(received.append)

    for page in Page:
        items = sidebar._nav_item.findItems(  # type: ignore[attr-defined]
            page.value,
            QtCore.Qt.MatchFlag.MatchExactly,
        )
        assert items
        item = items[0]

        sidebar._nav_item.setCurrentItem(item)  # type: ignore[attr-defined]
        sidebar._nav_item.itemClicked.emit(item)  # type: ignore[attr-defined]

    assert received == list(Page)


def test_sidebar_logo_emits_navigate_dashboard(
    qcoreapp: QtCore.QCoreApplication,
) -> None:
    sidebar = Sidebar()
    received: list[Page] = []
    sidebar.navigate.connect(received.append)

    sidebar.logo.clicked.emit()  # type: ignore[attr-defined]

    assert received == [Page.DASHBOARD]
