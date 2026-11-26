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
        hevc: bool = False,
    ) -> list[str]:

        return [

            "ffmpeg",

            "-y",

            "-rtsp_transport", "tcp",

            "-fflags", "+genpts+discardcorrupt",

            "-err_detect", "ignore_err",

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
            # Kopiertes H.265 als hvc1 kennzeichnen, damit Safari und iOS
            # die MP4-Datei direkt abspielen können.
            *(
                ["-tag:v", "hvc1"]
                if hevc and not transcode_video
                else []
            ),
            "-c:a", "aac" if transcode_audio else "copy",
            "-movflags", "+faststart",
            "-f", "mp4",

            str(filename),

        ]
