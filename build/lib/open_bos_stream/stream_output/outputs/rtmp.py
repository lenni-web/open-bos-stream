from open_bos_stream.core.models import (
    AppConfig,
    StreamOutputConfig,
)

from .base import BaseOutput


class RTMPOutput(BaseOutput):

    schemes = ("rtmp://", "rtmps://")

    def build(
        self,
        config: AppConfig,
        output: StreamOutputConfig,
    ) -> list[str]:
        return self._command(config, output, ["-f", "flv"], output.url)
