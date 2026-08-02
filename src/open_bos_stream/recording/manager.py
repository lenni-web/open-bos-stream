"""
Recording Manager

Zentrale Steuerung der Videoaufzeichnung.
"""

from __future__ import annotations

from pathlib import Path

from open_bos_stream.recording.command import RecordingCommandBuilder
from open_bos_stream.recording.process import RecordingProcess
class RecordingManager:

    def __init__(self) -> None:

        self._builder = RecordingCommandBuilder()

        self._process = RecordingProcess()

    @property
    def running(self) -> bool:

        return self._process.running

    @property
    def pid(self) -> int | None:

        return self._process.pid

    def start(
        self,
        filename: Path,
        input_url: str,
        *,
        transcode_video: bool = False,
        transcode_audio: bool = False,
    ) -> bool:

        if self.running:
            return True

        command = self._builder.build(
            filename,
            input_url,
            transcode_video=transcode_video,
            transcode_audio=transcode_audio,
        )

        self._process.start(command)

        return self.running

    def stop(self) -> bool:

        self._process.stop()

        return not self.running
