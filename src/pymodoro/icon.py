from pathlib import Path

from pymodoro.session import SessionPhase

# isort: split
from PySide6 import QtGui

_ICON_DIR = Path(__file__).resolve().parents[2] / "assets" / "icons"
_PHASE_ICON_FILES = {
    SessionPhase.WORK: _ICON_DIR / "icon-work.svg",
    SessionPhase.BREAK: _ICON_DIR / "icon-break.svg",
    SessionPhase.PAUSE: _ICON_DIR / "icon-paused.svg",
}


def phase_icon(phase: SessionPhase | None = None) -> QtGui.QIcon:
    if phase is None:
        phase = SessionPhase.BREAK
    svg_path = _PHASE_ICON_FILES.get(phase, _PHASE_ICON_FILES[SessionPhase.BREAK])
    return QtGui.QIcon(str(svg_path))
