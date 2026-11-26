from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)

from open_bos_stream.core.models import (
    AppConfig,
    StreamOutputConfig,
)

from .base import BaseOutput


class SRTOutput(BaseOutput):

    schemes = ("srt://",)

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
        # SRT-Puffer in Mikrosekunden (FFmpeg/libsrt): 400 ms gleichen
        # Mobilfunk-Paketverluste aus, ohne viel Verzögerung zu erzeugen.
        parameters.setdefault("latency", "400000")
        srt_url = urlunsplit((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(parameters),
            parsed.fragment,
        ))
        return self._command(
            config,
            output,
            [
                # Pakete sofort weitergeben statt im Muxer zu sammeln.
                "-flush_packets", "1",
                "-muxdelay", "0",
                "-muxpreload", "0",
                "-f", "mpegts",
            ],
            srt_url,
            input_options=["-fflags", "nobuffer"],
        )
