"""
FFmpeg Recording Command Builder
"""

from __future__ import annotations

from pathlib import Path

from open_bos_stream.core.models import AppConfig


class RecordingCommandBuilder:

    def __init__(self, config: AppConfig) -> None:

        self._config = config

    def build(self, filename: Path) -> list[str]:

        stream = self._config.stream

        return [

            "ffmpeg",

            "-y",

            "-rtsp_transport", "tcp",

            "-i",
            stream.rtsp_url,

            "-c", "copy",

            str(filename),

        ]
