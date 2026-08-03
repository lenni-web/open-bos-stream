"""
Streaming Output Manager
"""

from __future__ import annotations

from open_bos_stream.core.models import (
    AppConfig,
    StreamOutputConfig,
)

from open_bos_stream.stream_output.command import (
    StreamOutputCommandBuilder,
)

from open_bos_stream.stream_output.process import (
    StreamOutputProcess,
)


class StreamOutputManager:
    """Verwaltet alle konfigurierten Streaming Outputs."""

    def __init__(
        self,
        config: AppConfig,
    ) -> None:

        self._outputs = {}

        self._processes = {}

        self.reload(config)

    # ---------------------------------------------------------
    # Konfiguration neu laden
    # ---------------------------------------------------------

    def reload(
        self,
        config: AppConfig,
    ) -> None:

        self._builder = StreamOutputCommandBuilder(config)

        configured = {
            output.name: output
            for output in config.stream_outputs
        }

        #
        # Entfernte Outputs stoppen
        #

        for name in list(self._outputs.keys()):

            if name not in configured:

                process = self._processes.get(name)

                if process:

                    process.stop()

                self._outputs.pop(name, None)

                self._processes.pop(name, None)

        #
        # Neue / geänderte Outputs übernehmen
        #

        for name, output in configured.items():

            previous = self._outputs.get(name)

            if previous is not None and previous != output:
                process = self._processes.get(name)
                if process and process.running:
                    process.stop()

            self._outputs[name] = output

            if name not in self._processes:

                self._processes[name] = StreamOutputProcess()

    # ---------------------------------------------------------
    # Konfiguration
    # ---------------------------------------------------------

    def output(
        self,
        name: str,
    ) -> StreamOutputConfig | None:

        return self._outputs.get(name)

    def outputs(
        self,
    ) -> list[StreamOutputConfig]:

        return list(self._outputs.values())

    # ---------------------------------------------------------
    # Prozesse
    # ---------------------------------------------------------

    def process(
        self,
        name: str,
    ) -> StreamOutputProcess | None:

        return self._processes.get(name)

    def running(
        self,
        name: str,
    ) -> bool:

        process = self.process(name)

        return process.running if process else False

    def pid(
        self,
        name: str,
    ) -> int | None:

        process = self.process(name)

        return process.pid if process else None

    def last_error(
        self,
        name: str,
    ) -> str | None:
        process = self.process(name)
        return process.last_error if process else None

    # ---------------------------------------------------------
    # Steuerung
    # ---------------------------------------------------------

    def start(
        self,
        name: str,
    ) -> bool:

        output = self.output(name)

        process = self.process(name)

        if output is None or process is None:
            return False

        if process.running:
            return True

        command = self._builder.build(output)

        print(
            f"Starting output '{output.name}' "
            f"({output.type})..."
        )

        process.start(command)

        if not process.running:
            raise RuntimeError(
                process.last_error
                or "Streaming Output wurde unerwartet beendet."
            )

        return True

    def stop(
        self,
        name: str,
    ) -> bool:

        process = self.process(name)

        if process is None:
            return False

        process.stop()

        return not process.running

    def stop_all(self) -> None:

        for process in self._processes.values():

            process.stop()
