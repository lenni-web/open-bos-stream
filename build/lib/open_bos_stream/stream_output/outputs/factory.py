from open_bos_stream.stream.exceptions import ConfigurationError
from open_bos_stream.core.models import StreamOutputConfig

from .base import BaseOutput
from .rtmp import RTMPOutput
from .rtsp import RTSPOutput
from .srt import SRTOutput

class OutputFactory:

    @staticmethod
    def create(
        output: StreamOutputConfig,
    ) -> BaseOutput:

        match output.type.lower():

            case "rtmp":
                return RTMPOutput()

            case "srt":
                return SRTOutput()

            case "rtsp":
                return RTSPOutput()

        raise ConfigurationError(
            f"Unsupported output type: {output.type}"
        )