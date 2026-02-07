from __future__ import annotations

import pytest
from PySide6 import QtCore


@pytest.fixture(scope="session")
def qcoreapp() -> QtCore.QCoreApplication:
    app = QtCore.QCoreApplication.instance()
    if app is None:
        app = QtCore.QCoreApplication([])
    return app
