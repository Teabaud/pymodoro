import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from pymodoro.app_ui import AppWindow
from pymodoro.settings import load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = PROJECT_ROOT / "test_settings.yaml"


def main() -> int:
    """
    Dev-only entry point that constructs and shows the app window.

    Run this via the reloader script in the same directory, or directly with:
        python drafts/app_constructor.py
    """

    app = QApplication(sys.argv)
    settings = load_settings(SETTINGS_PATH)
    window = AppWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
