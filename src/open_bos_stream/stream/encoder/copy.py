"""
FFmpeg Stream Copy Encoder
"""

from __future__ import annotations

from open_bos_stream.stream.encoder.base import Encoder

from open_bos_stream.stream.video_formats import (
    VideoFormat,
)

class CopyEncoder(
    Encoder,
):

    codec = "copy"

    @classmethod
    def supports(
        cls,
        formats: list[VideoFormat],
    ) -> bool:

        return any(

            fmt in (
                VideoFormat.H264,
                VideoFormat.HEVC,
            )

            for fmt in formats

        )

    def build_args(
        self,
    ) -> list[str]:
        """Erzeugt FFmpeg-Argumente für Stream Copy."""
        return [
            "-c:v",
            "copy",
        ]


    def build(
        self,
    ) -> list[str]:
        return self.build_args()