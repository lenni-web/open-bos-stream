from __future__ import annotations

from open_bos_stream.core.models import SourceConfig
from open_bos_stream.stream.video_formats import (
    VideoFormat,
)
from open_bos_stream.stream.exceptions import (
    ConfigurationError,
)
from .base import InputBuilder
from .registry import registry


class RTMPInputBuilder(InputBuilder):

    type = "rtmp"

    name = "RTMP Stream"

    fields = [

        {
            "name": "url",
            "label": "RTMP URL",
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

    def output_formats(
        self,
        source: SourceConfig,
    ) -> list[VideoFormat]:
        """
        RTMP transportiert bereits kodierte Videostreams.
        """

        return [
            VideoFormat.H264,
            VideoFormat.HEVC,
        ]

    def validate(
        self,
        source: SourceConfig,
    ) -> None:

        if not source.url:

            raise ConfigurationError(
                "RTMP URL is required."
            )

        if not source.url.startswith(
            "rtmp://"
        ):

            raise ConfigurationError(
                "Invalid RTMP URL."
            )

    def capability_fields(
        self,
    ) -> list[str]:

        return [

            "url",

        ]

registry.register(
    RTMPInputBuilder(),
)