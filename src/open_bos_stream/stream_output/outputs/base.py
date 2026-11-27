from abc import ABC, abstractmethod

from open_bos_stream.core.models import (
    AppConfig,
    StreamOutputConfig,
)
from open_bos_stream.stream.exceptions import ConfigurationError
from open_bos_stream.stream_output.audio.factory import (
    AudioFactory,
)


class BaseOutput(ABC):
    """Gemeinsamer FFmpeg-Aufbau aller Streaming-Ausgänge.

    Jeder Ausgang liest die gewählte Drohne vom lokalen RTSP-Viewerpfad,
    übernimmt das Video unverändert und unterscheidet sich nur in Container
    und Ziel-URL.
    """

    schemes: tuple[str, ...] = ()

    def validate(
        self,
        output: StreamOutputConfig,
    ) -> None:
        if not output.url:
            raise ConfigurationError(
                "Output URL is required."
            )
        if not output.url.startswith(self.schemes):
            raise ConfigurationError(
                f"Invalid {output.type.upper()} URL."
            )

    @abstractmethod
    def build(
        self,
        config: AppConfig,
        output: StreamOutputConfig,
    ) -> list[str]:
        ...

    @staticmethod
    def _command(
        config: AppConfig,
        output: StreamOutputConfig,
        output_options: list[str],
        target: str,
        input_options: list[str] | None = None,
    ) -> list[str]:
        source = config.stream_output_source(output)
        input_url = (
            f"rtsp://127.0.0.1:8554/{source.viewer_path}"
            if source is not None
            else config.stream.rtsp_url
        )
        audio_command = AudioFactory.create(output.audio).build()

        return [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            *(input_options or []),
            "-i", input_url,
            *audio_command.inputs,
            *audio_command.mapping,
            "-c:v", "copy",
            *audio_command.options,
            *output_options,
            target,
        ]
