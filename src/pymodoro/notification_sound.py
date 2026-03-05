from __future__ import annotations

from pathlib import Path

# isort: split
from PySide6 import QtCore
from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

NOTIFICATION_SOUND_FILE_PATH = (
    Path(__file__).resolve().parents[2] / "assets" / "sounds" / "notification.wav"
)


class NotificationSoundPlayer(QtCore.QObject):
    def play(self) -> None:
        effect = QSoundEffect(self)
        effect.setSource(QUrl.fromLocalFile(NOTIFICATION_SOUND_FILE_PATH))
        effect.setLoopCount(1)
        effect.setVolume(0.8)
        effect.play()
