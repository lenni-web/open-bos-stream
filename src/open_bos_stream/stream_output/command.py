from open_bos_stream.core.models import (
    AppConfig,
    StreamOutputConfig,
)

from open_bos_stream.stream_output.outputs.factory import OutputFactory


class StreamOutputCommandBuilder:

    def __init__(
        self,
        config: AppConfig,
    ) -> None:

        self._config = config

    def build(
        self,
        output: StreamOutputConfig,
    ) -> list[str]:

        builder = OutputFactory.create(output)

        builder.validate(output)

        return builder.build(
            self._config,
            output,
        )