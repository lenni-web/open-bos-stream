"""
libx265 Encoder
"""

from __future__ import annotations

from open_bos_stream.stream.encoder.base import (
    Encoder,
)

from open_bos_stream.stream.video_formats import (
    VideoFormat,
)

class X265Encoder(
    Encoder,
):

    codec = "libx265"

    @classmethod
    def supports(
        cls,
        formats: list[VideoFormat],
    ) -> bool:

        return any(

            fmt in (

                VideoFormat.MJPEG,
                VideoFormat.YUYV422,
                VideoFormat.NV12,
                VideoFormat.H264,
                VideoFormat.HEVC,

            )

            for fmt in formats

        )

    def build(
        self,
    ) -> list[str]:

        return self.build_args(
            gop=True,
            extra_args=[
                "-x265-params",
                "bframes=0",
            ],
        )