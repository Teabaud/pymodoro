from __future__ import annotations

from pymodoro.app import PomodoroApp


def main() -> int:
    app = PomodoroApp()
    return app.launch()


if __name__ == "__main__":
    raise SystemExit(main())
