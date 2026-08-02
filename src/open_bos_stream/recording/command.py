"""
FFmpeg Recording Command Builder
"""

from __future__ import annotations

from pathlib import Path

class RecordingCommandBuilder:
    def build(
        self,
        filename: Path,
        input_url: str,
        *,
        transcode_video: bool = False,
        transcode_audio: bool = False,
    ) -> list[str]:

        return [

            "ffmpeg",

            "-y",

            "-rtsp_transport", "tcp",

            "-i",
            input_url,

            "-map", "0:v:0",
            "-map", "0:a:0?",
            "-c:v", "libx264" if transcode_video else "copy",
            *(
                ["-preset", "ultrafast", "-tune", "zerolatency", "-pix_fmt", "yuv420p"]
                if transcode_video
                else []
            ),
            "-c:a", "aac" if transcode_audio else "copy",
            "-movflags", "+faststart",

            str(filename),

        ]
