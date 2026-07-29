"""
Streaming Output Service
"""

from __future__ import annotations

from open_bos_stream.core.models import AppConfig

from open_bos_stream.stream_output.models import (
    StreamOutputStatus,
)
from open_bos_stream.mediamtx.client import MediaMTXClient
from open_bos_stream.stream_output.manager import (
    StreamOutputManager,
)


class StreamOutputService:
    """Geschäftslogik für Streaming Outputs."""

    def __init__(
        self,
        config: AppConfig,
        mediamtx: MediaMTXClient,
        manager: StreamOutputManager,
    ) -> None:

        self._config = config

        self._mediamtx = mediamtx

        self._manager = manager
    # ---------------------------------------------------------
    # Steuerung
    # ---------------------------------------------------------

    def start(
        self,
        name: str,
    ) -> None:

        output = self._manager.output(name)

        if output is None:
            raise RuntimeError(
                "Streaming Output nicht gefunden."
            )

        if not output.enabled:
            raise RuntimeError(
                "Streaming Output ist deaktiviert."
            )

        path = self._mediamtx.path(
            self._config.stream.name
        )

        if path is None:
            raise RuntimeError(
                "Kein aktiver Stream vorhanden."
            )

        if not path.get(
            "ready",
            False,
        ):
            raise RuntimeError(
                "Stream ist nicht bereit."
            )

        try:
            self._manager.start(name)
        except RuntimeError as exc:
            detail = str(exc).strip()
            lowered = detail.lower()

            if "connection refused" in lowered:
                advice = (
                    "Der SRT-Zielserver lehnt die Verbindung ab. "
                    "Host, Port und Listener prüfen."
                )
            elif (
                "timed out" in lowered
                or "connection timeout" in lowered
            ):
                advice = (
                    "Zeitüberschreitung beim SRT-Verbindungsaufbau. "
                    "Netzwerk, Firewall und Zielport prüfen."
                )
            elif "no route to host" in lowered:
                advice = (
                    "Der SRT-Zielserver ist über das Netzwerk "
                    "nicht erreichbar."
                )
            elif "invalid argument" in lowered:
                advice = (
                    "SRT-Adresse oder Verbindungsparameter sind ungültig."
                )
            else:
                advice = "FFmpeg konnte den Ausgang nicht starten."

            raise RuntimeError(
                f"{advice}\n{detail}"
            ) from exc

    def stop(
        self,
        name: str,
    ) -> None:

        self._manager.stop(
            name
        )

    def stop_all(
        self,
    ) -> None:

        self._manager.stop_all()

    # ---------------------------------------------------------
    # Status
    # ---------------------------------------------------------

    @property
    def status(
        self,
    ) -> list[StreamOutputStatus]:

        result = []

        for output in self._manager.outputs():

            result.append(

                StreamOutputStatus(

                    name=output.name,

                    enabled=output.enabled,

                    running=self._manager.running(
                        output.name
                    ),

                    pid=self._manager.pid(
                        output.name
                    ),

                    error=self._manager.last_error(
                        output.name
                    ),

                )

            )

        return result
