# Pymodoro

A lightweight system-tray Pomodoro timer built with PySide6 (Qt6). See `README.md` for standard setup and usage.

## Cursor Cloud specific instructions

### Services

| Service | Description |
|---------|-------------|
| Pymodoro (desktop app) | Single PySide6/Qt6 system-tray application — no backend, database, or external services |

### Running commands

- **Install deps:** `poetry install` (uses `pyproject.toml` + `poetry.lock`)
- **Tests:** `poetry run pytest` (headless via `QT_QPA_PLATFORM=offscreen` set in `tests/conftest.py`)
- **Lint:** `poetry run black --check src/ tests/` and `poetry run isort --check-only src/ tests/`
- **Run app:** `poetry run pymodoro` (requires a desktop session with system tray)

### Gotchas

- **System tray requirement:** The app checks `QSystemTrayIcon.isSystemTrayAvailable()` on startup and raises `RuntimeError` if no system tray is present. In headless/CI environments the app cannot launch via `poetry run pymodoro`. Tests are unaffected (they use the offscreen Qt platform).
- **StatusNotifier protocol:** PySide6/Qt6 uses the D-Bus StatusNotifier protocol (`org.kde.StatusNotifierWatcher`) for system tray icons, not the legacy XEmbed protocol. The XFCE4 panel's built-in `systray` plugin only supports XEmbed. To run the app with a visible tray icon in XFCE, install `xfce4-sntray-plugin` (`sudo apt-get install -y xfce4-sntray-plugin`), add it to the panel, and restart.
- **System Qt6 libraries:** PySide6 requires native shared libraries (`libegl1`, `libgl1`, `libxkbcommon0`, `libxkbcommon-x11-0`, `libxcb-cursor0`, etc.). These are pre-installed in the snapshot.
- **Testing UI components without system tray:** You can instantiate `SettingsWindow` and `CheckInScreen` directly from a Python script using `QApplication` without the tray check. See the test suite for examples.
