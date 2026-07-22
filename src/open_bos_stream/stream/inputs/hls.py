from __future__ import annotations

from open_bos_stream.core.models import SourceConfig
from open_bos_stream.stream.video_formats import (
    VideoFormat,
)

from .base import InputBuilder
from .registry import registry


class HLSInputBuilder(InputBuilder):

    type = "hls"

    name = "HLS Stream"

    fields = [

        {
            "name": "url",
            "label": "Playlist URL",
            "widget": "text",
        },

    ]

    def build(
        self,
        source: SourceConfig,
    ) -> list[str]:

        return [

            "-i",
            source.url,

        ]

    def capability_fields(
        self,
    ) -> list[str]:

        return [

            "url",

        ]

    def validate(
        self,
        source: SourceConfig,
    ) -> None:

        if not source.url:

            raise ValueError(
                "HLS URL fehlt."
            )

        if not source.url.startswith(
            "http://"
            "https://"
        ):

            raise ValueError(
                "Ungültige HLS-URL."
            )

    def output_formats(
        self,
        source: SourceConfig,
    ) -> list[VideoFormat]:

        return [
            VideoFormat.H264,
            VideoFormat.HEVC,
            VideoFormat.MJPEG,
        ]

registry.register(
    HLSInputBuilder(),
)