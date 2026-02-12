from __future__ import annotations

import os

import pytest
from PySide6 import QtCore, QtWidgets


@pytest.fixture(scope="session")
def qcoreapp() -> QtCore.QCoreApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QtCore.QCoreApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app
