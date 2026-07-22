from open_bos_stream.core.models import StreamConfig

from .base import BaseOutput


class RTSPOutput(BaseOutput):

    def build(
        self,
        output: StreamConfig,
    ) -> list[str]:

        return [

            "-f",
            "rtsp",

            output.rtsp_url,

        ]