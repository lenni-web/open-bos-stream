from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from open_bos_stream.core.models import SourceConfig
from open_bos_stream.stream.video_formats import (
    VideoFormat,
)
from open_bos_stream.stream.exceptions import (
    ConfigurationError,
)
from .base import InputBuilder
from .registry import registry


def repair_input_url(url: str) -> tuple[str, bool]:
    """Lokalen MediaMTX-RTMP-Pfad über seinen RTSP-Spiegel lesen."""

    parsed = urlparse(url)
    if (
        parsed.scheme == "rtmp"
        and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        and (parsed.port or 1935) == 1935
    ):
        host = parsed.hostname or "127.0.0.1"
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return (
            urlunparse((
                "rtsp",
                f"{host}:8554",
                parsed.path,
                "",
                "",
                "",
            )),
            True,
        )
    return url, False


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

        command = []

        if (
            getattr(source, "mode", None) == "copy_repair"
            or getattr(source, "profile", None) == "copy_repair"
        ):
            input_url, use_rtsp = repair_input_url(source.url)
            command.extend([
                "-thread_queue_size",
                "512",
                "-fflags",
                "+genpts+discardcorrupt+nobuffer",
                "-flags",
                "low_delay",
                "-use_wallclock_as_timestamps",
                "1",
            ])
            if use_rtsp:
                command.extend([
                    "-rtsp_transport",
                    "tcp",
                    "-max_delay",
                    "0",
                ])
        else:
            input_url = source.url

        command.extend([

            "-i",
            input_url,

        ])

        return command

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
