from open_bos_stream.stream.exceptions import ConfigurationError
from open_bos_stream.core.models import (
    AppConfig,
    StreamOutputConfig,
)

from .base import BaseOutput


class SRTOutput(BaseOutput):

    def validate(
        self,
        output: StreamOutputConfig,
    ) -> None:

        if not output.url:
            raise ConfigurationError(
                "Output URL is required."
            )

        if not output.url.startswith("srt://"):
            raise ConfigurationError(
                "Invalid SRT URL."
            )

    def build(
        self,
        config: AppConfig,
        output: StreamOutputConfig,
    ) -> list[str]:

        return [
            "ffmpeg",

            "-rtsp_transport",
            "tcp",

            "-i",
            config.stream.rtsp_url,

            "-c",
            "copy",

            "-f",
            "mpegts",

            output.url,
        ]