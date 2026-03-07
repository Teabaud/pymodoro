from pathlib import Path

import sounddevice as sd
import soundfile as sf

NOTIFICATION_SOUND_FILE_PATH = (
    Path(__file__).resolve().parents[2] / "assets" / "sounds" / "notification.wav"
)


class NotificationSoundPlayer:
    def __init__(self) -> None:
        data, samplerate = sf.read(NOTIFICATION_SOUND_FILE_PATH, dtype="float32")
        self._data = data
        self._samplerate = samplerate
        self._volume = 0.8
        
    def play(self) -> None:
        sd.play(self._data * self._volume, self._samplerate)
        