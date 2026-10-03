"""Originalstream für Aufnahmen und Snapshots bereitstellen.

Quellen mit Vorschauprofil liefern im Dashboard nur einen reduzierten
Viewerpfad. Für Medien wird stattdessen derselbe Hauptstream verwendet wie in
der Vollbildanzeige: bei RTMP-Vorschauprofilen der unveränderte
Publisherpfad, bei RTSP mit Vorschau-URL ein bedarfsgesteuerter Relay des
Kamera-Hauptstreams. Der Relay wird über eine Lease offen gehalten, die
während einer Aufnahme regelmäßig erneuert und danach freigegeben wird.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from open_bos_stream.core.models import SourceConfig


logger = logging.getLogger(__name__)

MAIN_STREAM_TIMEOUT_SECONDS = 8.0


@dataclass
class CaptureInput:
    source_id: str
    path_name: str
    path: dict | None
    full_quality: bool
    lease_id: str | None = None

    @property
    def url(self) -> str:
        return f"rtsp://127.0.0.1:8554/{self.path_name}"


class CaptureInputProvider:
    def __init__(
        self,
        mediamtx,
        relays=None,
        *,
        timeout: float = MAIN_STREAM_TIMEOUT_SECONDS,
        sleep=time.sleep,
    ) -> None:
        self._mediamtx = mediamtx
        self._relays = relays
        self._timeout = timeout
        self._sleep = sleep

    def open(self, source: SourceConfig) -> CaptureInput:
        """Hauptstream öffnen; bei Problemen auf den Viewerpfad ausweichen."""

        if (
            self._relays is None
            or source.fullscreen_viewer_path == source.viewer_path
        ):
            return self._viewer(source, full_quality=True)

        try:
            status = self._relays.acquire(source.id)
        except (KeyError, ValueError):
            return self._viewer(source, full_quality=False)

        lease_id = status["lease_id"]
        deadline = time.monotonic() + self._timeout
        try:
            while not status.get("ready") and time.monotonic() < deadline:
                self._sleep(0.5)
                status = self._relays.status(source.id, lease_id)
        except KeyError:
            status = {"ready": False}

        if status.get("ready"):
            path_name = source.fullscreen_viewer_path
            return CaptureInput(
                source_id=source.id,
                path_name=path_name,
                path=self._mediamtx.path(path_name),
                full_quality=True,
                lease_id=lease_id,
            )

        self._relays.release(source.id, lease_id)
        logger.warning(
            "Hauptstream der Quelle %s nicht verfügbar; Medien werden in "
            "Vorschauqualität erstellt.",
            source.id,
        )
        return self._viewer(source, full_quality=False)

    def renew(self, capture: CaptureInput) -> bool:
        """Lease des Hauptstreams verlängern."""

        if capture.lease_id is None or self._relays is None:
            return True
        try:
            self._relays.status(capture.source_id, capture.lease_id)
        except KeyError:
            return False
        return True

    def release(self, capture: CaptureInput | None) -> None:
        if (
            capture is None
            or capture.lease_id is None
            or self._relays is None
        ):
            return
        self._relays.release(capture.source_id, capture.lease_id)
        capture.lease_id = None

    def _viewer(
        self,
        source: SourceConfig,
        *,
        full_quality: bool,
    ) -> CaptureInput:
        return CaptureInput(
            source_id=source.id,
            path_name=source.viewer_path,
            path=self._mediamtx.path(source.viewer_path),
            full_quality=full_quality,
        )
