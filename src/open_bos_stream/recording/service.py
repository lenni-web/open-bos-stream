"""
Recording Service
"""

from __future__ import annotations

import time

from open_bos_stream.core.models import AppConfig
from open_bos_stream.mediamtx.client import MediaMTXClient
from open_bos_stream.recording.manager import RecordingManager
from open_bos_stream.recording.models import RecordingStatus
from open_bos_stream.recording.recorder import Recorder


class RecordingService:
    """Geschäftslogik für Videoaufzeichnungen."""

    def __init__(
        self,
        config: AppConfig,
        mediamtx: MediaMTXClient,
    ) -> None:

        self._config = config

        self._recorder = Recorder()

        self._manager = RecordingManager(config)

        self._status = RecordingStatus()

        self._mediamtx = mediamtx

    @property
    def status(self) -> RecordingStatus:
        """Aktuellen Aufnahmestatus zurückgeben."""

        self._status.recording = self._manager.running
        self._status.pid = self._manager.pid

        if (
            self._manager.running
            and self._status.started_at is not None
        ):
            self._status.duration = int(
                time.time() - self._status.started_at
            )

        return self._status

    def start(self) -> None:
        """Aufnahme starten."""

        if self._manager.running:
            return

        path = self._mediamtx.path(
            self._config.stream.name
        )

        if path is None:
            raise RuntimeError(
                f"Stream '{self._config.stream.name}' ist nicht verfügbar."
            )

        if not path.get("ready", False):
            raise RuntimeError(
                "Stream läuft nicht. Bitte zuerst den Stream starten."
            )

        filename = self._recorder.next_filename()

        self._manager.start(filename)

        self._status.filename = str(filename)
        self._status.started_at = time.time()
        self._status.duration = 0
        self._status.recording = True
        self._status.pid = self._manager.pid

    def stop(self) -> None:
        """Aufnahme stoppen."""

        self._manager.stop()

        self._status.recording = False
        self._status.started_at = None
        self._status.duration = 0
        self._status.pid = None
