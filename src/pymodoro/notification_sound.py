from __future__ import annotations

from pathlib import Path

from loguru import logger

# isort: split
from PySide6 import QtCore
from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

NOTIFICATION_SOUND_FILE_PATH = (
    Path(__file__).resolve().parents[2] / "assets" / "sounds" / "notification.wav"
)


class NotificationSoundPlayer(QtCore.QObject):
    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._sound_effect: QSoundEffect | None = None

    def play(self) -> None:
        if self._sound_effect is None:
            effect = QSoundEffect(self)
            effect.setSource(QUrl.fromLocalFile(NOTIFICATION_SOUND_FILE_PATH))
            effect.setLoopCount(1)
            effect.setVolume(0.8)
            self._sound_effect = effect
        self._sound_effect.play()
