"""
FFmpeg V4L2 M2M Encoder
"""

from __future__ import annotations

from open_bos_stream.stream.encoder.base import (
    Encoder,
)

from open_bos_stream.stream.video_formats import (
    VideoFormat,
)

class H264V4L2M2MEncoder(
    Encoder,
):

    codec = "h264_v4l2m2m"

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

        return self.build_args()