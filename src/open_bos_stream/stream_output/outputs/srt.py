from open_bos_stream.stream.exceptions import ConfigurationError
from open_bos_stream.core.models import (
    AppConfig,
    StreamOutputConfig,
)
from open_bos_stream.stream_output.audio.factory import (
    AudioFactory,
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

        separator = "&" if "?" in output.url else "?"

        srt_url = (
            f"{output.url}{separator}"
            "mode=caller"
            "&transtype=live"
            "&streamid=publish:live"
            "&pkt_size=1316"
        )

        audio = AudioFactory.create(
            output.audio,
        )

        audio_command = audio.build()

        command = [
            "ffmpeg",

            "-rtsp_transport",
            "tcp",

            "-i",
            config.stream.rtsp_url,
        ]

        command.extend(audio_command.inputs)
        command.extend(audio_command.mapping)

        command.extend([
            "-c:v",
            "copy",
        ])

        command.extend(audio_command.options)

        command.extend([
            "-f",
            "mpegts",

            srt_url,
        ])

        return command
