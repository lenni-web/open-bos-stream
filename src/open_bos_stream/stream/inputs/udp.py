from __future__ import annotations

from open_bos_stream.core.models import SourceConfig
from open_bos_stream.stream.video_formats import (
    VideoFormat,
)
from .base import InputBuilder
from .registry import registry


class UDPInputBuilder(InputBuilder):

    type = "udp"

    name = "UDP Stream"

    fields = [

        {
            "name": "url",
            "label": "UDP URL",
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
                "UDP URL fehlt."
            )

        if not source.url.startswith(
            "udp://"
        ):

            raise ValueError(
                "Ungültige UDP-URL."
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
    UDPInputBuilder(),
)