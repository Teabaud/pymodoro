import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from pymodoro.dashboard.dashboard_ui import DashboardWindow
from pymodoro.settings import load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = PROJECT_ROOT / "test_settings.yaml"


def main() -> int:
    """
    Dev-only entry point that constructs and shows the dashboard window.

    Run this via the reloader script in the same directory, or directly with:
        python drafts/dashboard_constructor.py
    """

    app = QApplication(sys.argv)
    settings = load_settings(SETTINGS_PATH)
    window = DashboardWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
