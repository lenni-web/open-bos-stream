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
        srt_url = urlunsplit((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(parameters),
            parsed.fragment,
        ))
        return self._command(config, output, ["-f", "mpegts"], srt_url)
