from __future__ import annotations

from open_bos_stream.core.models import SourceConfig
from open_bos_stream.stream.video_formats import (
    VideoFormat,
)
from .base import InputBuilder
from .registry import registry


class HTTPInputBuilder(InputBuilder):

    type = "http"

    name = "HTTP Stream"

    fields = [

        {
            "name": "url",
            "label": "HTTP URL",
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
                "HTTP URL fehlt."
            )

        if not source.url.startswith(
            "http://"
            "https://"
        ):

            raise ValueError(
                "Ungültige HTTP-URL."
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
    HTTPInputBuilder(),
)