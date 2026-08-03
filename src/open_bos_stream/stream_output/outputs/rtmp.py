from open_bos_stream.stream.exceptions import ConfigurationError
from open_bos_stream.core.models import (
    AppConfig,
    StreamOutputConfig,
)
from open_bos_stream.stream_output.audio.factory import (
    AudioFactory,
)
from .base import BaseOutput

class RTMPOutput(BaseOutput):

    def validate(

        self,

        output: StreamOutputConfig,

    ) -> None:

        if not output.url:
            raise ConfigurationError(
                "Output URL is required."
            )

        if not output.url.startswith((
            "rtmp://",
            "rtmps://",
        )):

            raise ConfigurationError(
                "Invalid RTMP URL."
            )

    def build(
        self,
        config: AppConfig,
        output: StreamOutputConfig,
    ) -> list[str]:

        source = config.stream_output_source(output)
        input_url = (
            f"rtsp://127.0.0.1:8554/{source.viewer_path}"
            if source is not None
            else config.stream.rtsp_url
        )

        command = [

            "ffmpeg",

            "-rtsp_transport",
            "tcp",

            "-i",
            input_url,
        ]

        audio = AudioFactory.create(
            output.audio,
        )

        audio_command = audio.build()

        command.extend(audio_command.inputs)
        command.extend(audio_command.mapping)

        command.extend([
            "-c:v",
            "copy",
        ])

        command.extend(audio_command.options)

        command.extend([

            "-f",
            "flv",

            output.url,

        ])

        return command
