from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DRAFTS_DIR = PROJECT_ROOT / "drafts"

# Change this to point to any constructor script you want to play with.
TARGET_SCRIPT = DRAFTS_DIR / "dashboard_constructor.py"

# Directories to watch for .py changes.
WATCHED_DIRS = [
    PROJECT_ROOT / "src" / "pymodoro",
    DRAFTS_DIR,
]


class ReloadHandler(FileSystemEventHandler):
    def __init__(self) -> None:
        super().__init__()
        self.process: subprocess.Popen[bytes] | None = None
        self._start_child()

    def _start_child(self) -> None:
        if not TARGET_SCRIPT.exists():
            print(f"[reloader] Target script not found: {TARGET_SCRIPT}", flush=True)
            return
        print(f"[reloader] Starting: {TARGET_SCRIPT}", flush=True)
        self.process = subprocess.Popen(
            [sys.executable, str(TARGET_SCRIPT)],
            cwd=PROJECT_ROOT,
        )

    def _stop_child(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            print("[reloader] Stopping child process...", flush=True)
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("[reloader] Killing unresponsive child...", flush=True)
                self.process.kill()
        self.process = None

    def _restart_child(self) -> None:
        self._stop_child()
        self._start_child()

    def on_modified(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        if not str(event.src_path).endswith(".py"):
            return
        print(
            f"[reloader] Detected change in {event.src_path}, reloading...", flush=True
        )
        self._restart_child()


def main() -> None:
    """
    Dev-only reloader for tinkering with PySide6 windows.

    Run from the project root:
        python drafts/reloader.py

    By default it runs ``dashboard_constructor.py`` in this folder.
    Edit ``TARGET_SCRIPT`` above to point to another constructor script
    (e.g. a settings or check-in window constructor) and save; the next
    file change will restart the right target.
    """
    handler = ReloadHandler()
    observer = Observer()

    for directory in WATCHED_DIRS:
        observer.schedule(handler, str(directory), recursive=True)

    observer.start()
    print("[reloader] Watching for .py changes. Press Ctrl+C to stop.", flush=True)

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[reloader] Shutting down...", flush=True)
    finally:
        observer.stop()
        observer.join()
        handler._stop_child()


if __name__ == "__main__":
    main()
