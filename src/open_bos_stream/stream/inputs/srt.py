from __future__ import annotations

from open_bos_stream.core.models import SourceConfig

from .base import InputBuilder
from .registry import registry
from open_bos_stream.stream.video_formats import (
    VideoFormat,
)

class SRTInputBuilder(InputBuilder):

    type = "srt"

    name = "SRT Stream"

    fields = [

        {
            "name": "url",
            "label": "SRT URL",
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
                "SRT URL fehlt."
            )

        if not source.url.startswith(
            "srt://"
        ):

            raise ValueError(
                "Ungültige SRT-URL."
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
    SRTInputBuilder(),
)