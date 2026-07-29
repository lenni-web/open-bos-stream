from open_bos_stream.stream.exceptions import ConfigurationError
from open_bos_stream.core.models import (
    AppConfig,
    StreamOutputConfig,
)
from open_bos_stream.stream_output.audio.factory import (
    AudioFactory,
)
from .base import BaseOutput
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)


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

        parsed = urlsplit(output.url)
        parameters = dict(
            parse_qsl(
                parsed.query,
                keep_blank_values=True,
            )
        )
        parameters.setdefault("mode", "caller")
        parameters.setdefault("transtype", "live")
        parameters.setdefault("pkt_size", "1316")
        srt_url = urlunsplit((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(parameters),
            parsed.fragment,
        ))

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
