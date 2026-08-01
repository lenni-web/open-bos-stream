"""
FFmpeg Recording Command Builder
"""

from __future__ import annotations

from pathlib import Path

class RecordingCommandBuilder:
    def build(self, filename: Path, input_url: str) -> list[str]:

        return [

            "ffmpeg",

            "-y",

            "-rtsp_transport", "tcp",

            "-i",
            input_url,

            "-c", "copy",

            str(filename),

        ]
