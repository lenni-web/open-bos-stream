"""
Recording Manager

Zentrale Steuerung der Videoaufzeichnung.
"""

from __future__ import annotations

from pathlib import Path

from open_bos_stream.recording.command import RecordingCommandBuilder
from open_bos_stream.recording.process import RecordingProcess
from open_bos_stream.core.models import AppConfig

class RecordingManager:

    def __init__(
        self,
        config: AppConfig,
    ) -> None:

        self._builder = RecordingCommandBuilder(config)

        self._process = RecordingProcess()

    @property
    def running(self) -> bool:

        return self._process.running

    @property
    def pid(self) -> int | None:

        return self._process.pid

    def start(self, filename: Path) -> bool:

        if self.running:
            return True

        command = self._builder.build(filename)

        self._process.start(command)

        return self.running

    def stop(self) -> bool:

        self._process.stop()

        return not self.running

