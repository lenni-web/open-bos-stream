from open_bos_stream.core.models import (
    AppConfig,
    StreamOutputConfig,
)

from .base import BaseOutput


class RTSPOutput(BaseOutput):
    """Veröffentlicht die Quelle per RTSP-Publish (z. B. an einen
    MediaMTX- oder Wowza-Server)."""

    schemes = ("rtsp://", "rtsps://")

    def build(
        self,
        config: AppConfig,
        output: StreamOutputConfig,
    ) -> list[str]:
        return self._command(
            config,
            output,
            ["-f", "rtsp", "-rtsp_transport", "tcp"],
            output.url,
        )
