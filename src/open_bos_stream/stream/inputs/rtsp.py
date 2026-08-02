from __future__ import annotations

from open_bos_stream.core.models import (
    SourceConfig,
)

from open_bos_stream.stream.video_formats import (
    VideoFormat,
)

from .base import InputBuilder
from .registry import registry


class RTSPInputBuilder(InputBuilder):

    type = "rtsp"

    name = "RTSP Stream"

    fields = [

        {
            "name": "url",
            "label": "RTSP URL",
            "widget": "text",
        },

        {
            "name": "transport",
            "label": "Transport",
            "widget": "select",
            "options": [
                "tcp",
                "udp",
            ],
            "default": "tcp",
        },

    ]

    def output_formats(
        self,
        source: SourceConfig,
    ) -> list[VideoFormat]:

        #
        # RTSP transportiert in der Praxis
        # bereits komprimierte Videostreams.
        #
        return [
            VideoFormat.H264,
            VideoFormat.HEVC,
            VideoFormat.MJPEG,
        ]

    def build(
        self,
        source: SourceConfig,
    ) -> list[str]:

        transport = getattr(
            source,
            "transport",
            "tcp",
        )

        command = [
            "-rtsp_transport",
            transport,
        ]

        if getattr(source, "profile", None) == "copy_repair":
            command.extend([
                "-thread_queue_size",
                "512",
                "-fflags",
                "+genpts+discardcorrupt",
                "-use_wallclock_as_timestamps",
                "1",
            ])

        command.extend([
            "-i",
            source.url,
        ])

        return command

    def validate(
        self,
        source: SourceConfig,
    ) -> None:

        if not source.url:

            raise ValueError(
                "RTSP URL fehlt."
            )

        if not source.url.startswith(
            "rtsp://"
        ):

            raise ValueError(
                "Ungültige RTSP-URL."
            )

    def capability_fields(
        self,
    ) -> list[str]:

        return [

            "url",

        ]

registry.register(
    RTSPInputBuilder(),
)
