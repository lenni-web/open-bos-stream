"""
Recording Service

Jede Drohne hat einen eigenen Aufnahmekanal. Die gewählte Medienquelle
lässt sich manuell aufnehmen; Drohnen in ``automatic_source_ids`` starten
und beenden ihre Aufnahme selbstständig mit dem Eingangssignal. Es laufen
höchstens vier Aufnahmen gleichzeitig.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import RLock

from open_bos_stream.core.models import AppConfig
from open_bos_stream.media.capture import CaptureInput, CaptureInputProvider
from open_bos_stream.media.storage import MediaStorageService
from open_bos_stream.mediamtx.client import MediaMTXClient
from open_bos_stream.recording.manager import RecordingManager
from open_bos_stream.recording.models import RecordingStatus
from open_bos_stream.recording.recorder import Recorder

AUTOMATIC_RETRY_SECONDS = 5
AUTOMATIC_OFFLINE_SAMPLES = 2
CAPTURE_RENEW_SECONDS = 10


@dataclass
class _Channel:
    """Aufnahmezustand einer einzelnen Quelle."""

    source_id: str
    manager: object
    status: RecordingStatus = field(default_factory=RecordingStatus)
    capture: CaptureInput | None = None
    capture_renewed_at: float = 0.0
    offline_samples: int = 0
    last_attempt: float = 0.0
    started_automatically: bool = False


class RecordingService:
    """Geschäftslogik für Videoaufzeichnungen."""

    def __init__(
        self,
        config: AppConfig,
        mediamtx: MediaMTXClient,
        storage: MediaStorageService | None = None,
        relays=None,
        manager_factory=RecordingManager,
        event_log=None,
    ) -> None:
        self._config = config
        self._recorder = Recorder()
        self._manager_factory = manager_factory
        self._mediamtx = mediamtx
        self._storage = storage
        self._capture = CaptureInputProvider(mediamtx, relays)
        self._channels: dict[str, _Channel] = {}
        self._events = event_log
        self._control_lock = RLock()

    # ------------------------------------------------------------------
    # Quellen und Kanäle
    # ------------------------------------------------------------------

    def _enabled_sources(self) -> list:
        return [item for item in self._config.sources if item.enabled]

    def _source(self, source_id: str):
        return next(
            (item for item in self._enabled_sources() if item.id == source_id),
            None,
        )

    def _selected_source(self):
        selected_id = self._config.media_capture.source_id
        source = self._source(selected_id) if selected_id else None
        if source is None:
            sources = self._enabled_sources()
            source = sources[0] if sources else None
        if source is None:
            raise RuntimeError("Keine aktive Drohne konfiguriert.")
        return source

    def automatic_source_ids(self) -> list[str]:
        enabled = {item.id for item in self._enabled_sources()}
        return [
            item
            for item in self._config.media_capture.automatic_source_ids
            if item in enabled
        ]

    def is_automatic(self, source_id: str) -> bool:
        return source_id in self.automatic_source_ids()

    def _channel(self, source_id: str) -> _Channel:
        channel = self._channels.get(source_id)
        if channel is None:
            channel = _Channel(
                source_id=source_id,
                manager=self._manager_factory(),
            )
            self._channels[source_id] = channel
        return channel

    def _running_count(self) -> int:
        return sum(
            1 for channel in self._channels.values() if channel.manager.running
        )

    @property
    def recording_active(self) -> bool:
        return self._running_count() > 0

    def _event(self, level: str, message: str, actor: str | None = None) -> None:
        if self._events is not None:
            self._events.record(level, message, actor=actor)

    def _report_outcome(
        self,
        channel: _Channel,
        actor: str | None = None,
    ) -> None:
        """Abschluss einer Aufnahme ins Ereignisprotokoll schreiben."""

        outcome = getattr(channel.manager, "last_outcome", None)
        name = channel.status.source_name or channel.source_id
        if outcome is None:
            self._event("info", f"⏹ Aufnahme beendet · {name}", actor)
            return
        file_name = (
            outcome.filename.rsplit("/", 1)[-1] if outcome.filename else None
        )
        saved = f" · {file_name}" if file_name else ""
        if outcome.reason == "stream_interrupted":
            self._event(
                "warning",
                f"⚠ Aufnahme durch Streamabbruch beendet · {name}{saved}",
            )
        elif outcome.reason == "failed":
            self._event(
                "error",
                f"⛔ Aufnahme fehlgeschlagen, keine gültige Datei · {name}",
            )
        elif outcome.reason == "storage_low":
            self._event(
                "warning",
                f"⚠ Aufnahme wegen Speichermangel beendet · {name}{saved}",
            )
        else:
            self._event(
                "info",
                f"⏹ Aufnahme gespeichert · {name}{saved}",
                actor,
            )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def _refresh(self, channel: _Channel) -> RecordingStatus:
        status = channel.status
        manager = channel.manager
        status.recording = manager.running
        status.pid = manager.pid
        status.mode = (
            "automatic" if self.is_automatic(channel.source_id) else "manual"
        )
        status.automatic_waiting = (
            status.mode == "automatic" and not manager.running
        )

        outcome = getattr(manager, "last_outcome", None)
        if outcome is not None:
            status.end_reason = outcome.reason
            status.end_message = outcome.message
            status.completed_filename = outcome.filename
            status.finished_at = outcome.finished_at
            if not manager.running:
                status.started_at = None

        if manager.running and status.started_at is not None:
            status.duration = int(time.time() - status.started_at)
        return status

    @property
    def status(self) -> RecordingStatus:
        """Status der gewählten Medienquelle (Balken in der Übersicht)."""

        try:
            source = self._selected_source()
        except RuntimeError:
            return RecordingStatus()
        status = self._refresh(self._channel(source.id))
        if status.source_id is None:
            status.source_id = source.id
            status.source_name = source.name
        return status

    def statuses(self) -> list[RecordingStatus]:
        """Status aller aktiven Quellen, für Kacheln und Benachrichtigungen."""

        result = []
        for source in self._enabled_sources():
            status = self._refresh(self._channel(source.id))
            status.source_id = source.id
            status.source_name = source.name
            result.append(status)
        return result

    # ------------------------------------------------------------------
    # Steuerung
    # ------------------------------------------------------------------

    def start(
        self,
        *,
        automatic: bool = False,
        source_id: str | None = None,
        actor: str | None = None,
    ) -> None:
        """Aufnahme starten (ohne Quelle: gewählte Medienquelle)."""

        with self._control_lock:
            source = (
                self._source(source_id)
                if source_id
                else self._selected_source()
            )
            if source is None:
                raise RuntimeError("Drohne ist nicht aktiv.")
            self._start(source, automatic=automatic, actor=actor)

    def _start(
        self,
        source,
        *,
        automatic: bool,
        actor: str | None = None,
    ) -> None:
        if self.is_automatic(source.id) and not automatic:
            raise RuntimeError(
                "Die Aufnahme wird automatisch durch das Eingangssignal gesteuert."
            )

        channel = self._channel(source.id)
        if channel.manager.running:
            return

        path = self._mediamtx.path(source.viewer_path)
        if path is None:
            raise RuntimeError(
                f"Drohne '{source.name}' ist nicht verfügbar."
            )
        if not path.get("ready", False):
            raise RuntimeError(
                "Stream läuft nicht. Bitte zuerst den Stream starten."
            )

        if self._storage is not None:
            self._storage.ensure_capacity()

        # Aufnahmen verwenden den Originalstream, nicht die Vorschau.
        capture = self._capture.open(source)
        try:
            filename = self._recorder.next_filename(source.id)
            details = capture.path or path

            tracks = [
                str(item).lower() for item in details.get("tracks", [])
            ]
            video_codec = str(details.get("codec") or "").lower()
            h264 = video_codec in {"h264", "avc"} or any(
                "h264" in item for item in tracks
            )
            hevc = video_codec in {"h265", "hevc"} or any(
                "h265" in item or "hevc" in item for item in tracks
            )
            audio_tracks = [
                item for item in tracks
                if not any(
                    video in item
                    for video in ("h264", "h265", "avc", "hevc")
                )
            ]
            browser_audio = not audio_tracks or any(
                "aac" in item or "mpeg-4 audio" in item
                for item in audio_tracks
            )

            # H.264 und H.265 werden unverändert übernommen. H.265 wird erst
            # bei Bedarf für die Browserwiedergabe umgewandelt, damit 4K-
            # Originale keine dauerhafte Live-Transkodierung erfordern.
            channel.manager.start(
                filename,
                capture.url,
                transcode_video=not (h264 or hevc),
                transcode_audio=not browser_audio,
                hevc=hevc and not h264,
            )
        except Exception:
            self._capture.release(capture)
            raise

        channel.capture = capture
        channel.capture_renewed_at = time.monotonic()
        channel.started_automatically = automatic
        status = channel.status
        status.full_quality = capture.full_quality
        status.filename = str(filename)
        status.started_at = time.time()
        status.duration = 0
        status.recording = True
        status.pid = channel.manager.pid
        status.source_id = source.id
        status.source_name = source.name
        status.end_reason = None
        status.end_message = None
        status.completed_filename = None
        status.finished_at = None
        status.automatic_error = None
        status.automatic_waiting = False
        self._event(
            "success",
            f"⏺ Aufnahme gestartet · {source.name}"
            + (" · automatisch" if automatic else ""),
            actor=None if automatic else actor,
        )

    def stop(
        self,
        *,
        automatic: bool = False,
        source_id: str | None = None,
        actor: str | None = None,
    ) -> None:
        """Aufnahme stoppen (ohne Quelle: gewählte Medienquelle)."""

        with self._control_lock:
            if source_id is None:
                source_id = self._selected_source().id
            if self.is_automatic(source_id) and not automatic:
                raise RuntimeError(
                    "Die Aufnahme wird automatisch durch das Eingangssignal "
                    "gesteuert."
                )
            self._stop(self._channel(source_id), actor=actor)

    def _stop(
        self,
        channel: _Channel,
        *,
        actor: str | None = None,
        **stop_kwargs,
    ) -> None:
        was_running = channel.manager.running
        try:
            channel.manager.stop(**stop_kwargs)
        finally:
            self._release_capture(channel)
            channel.started_automatically = False
            status = channel.status
            status.recording = False
            status.started_at = None
            status.duration = 0
            status.pid = None
        if was_running:
            self._report_outcome(channel, actor)

    def stop_all(self) -> None:
        """Alle laufenden Aufnahmen sauber abschließen (z. B. beim Beenden)."""

        with self._control_lock:
            for channel in list(self._channels.values()):
                if channel.manager.running:
                    self._stop(channel)

    def stop_for_storage(self, message: str) -> None:
        """Laufende Aufnahmen wegen Speichermangel sauber abschließen."""

        with self._control_lock:
            for channel in list(self._channels.values()):
                if channel.manager.running:
                    self._stop(
                        channel,
                        reason="storage_low",
                        message=message,
                    )

    # ------------------------------------------------------------------
    # Pflege und Automatik
    # ------------------------------------------------------------------

    def maintain(self) -> None:
        """Periodische Pflege: Hauptstreams halten und Automatik abgleichen."""

        with self._control_lock:
            for channel in list(self._channels.values()):
                self._maintain_capture(channel)
        self.reconcile_automatic()

    def _maintain_capture(self, channel: _Channel) -> None:
        if channel.capture is None:
            return
        if not channel.manager.running:
            # Aufnahme wurde ohne Bedienaktion beendet (z. B. Streamabbruch).
            self._release_capture(channel)
            channel.started_automatically = False
            self._report_outcome(channel)
            return
        now = time.monotonic()
        if now - channel.capture_renewed_at >= CAPTURE_RENEW_SECONDS:
            self._capture.renew(channel.capture)
            channel.capture_renewed_at = now

    def _release_capture(self, channel: _Channel) -> None:
        self._capture.release(channel.capture)
        channel.capture = None
        channel.status.full_quality = None

    def reconcile_automatic(self) -> None:
        """Aufnahmen aller automatischen Quellen an ihr Signal angleichen."""

        with self._control_lock:
            automatic = set(self.automatic_source_ids())
            enabled = {item.id: item for item in self._enabled_sources()}

            # Automatisch gestartete Aufnahmen beenden, wenn die Quelle aus
            # der Automatik genommen oder deaktiviert wurde.
            for source_id, channel in list(self._channels.items()):
                if (
                    channel.manager.running
                    and channel.started_automatically
                    and (source_id not in automatic or source_id not in enabled)
                ):
                    self._stop(channel)
                    channel.offline_samples = 0

            for source_id in automatic:
                self._reconcile_source(enabled[source_id])

    def _reconcile_source(self, source) -> None:
        channel = self._channel(source.id)
        status = channel.status
        path = self._mediamtx.path(source.viewer_path)
        ready = bool(path and path.get("ready", False))

        if channel.manager.running:
            if ready:
                channel.offline_samples = 0
                status.automatic_error = None
                return
            channel.offline_samples += 1
            if channel.offline_samples >= AUTOMATIC_OFFLINE_SAMPLES:
                self._stop(channel)
                channel.offline_samples = 0
            return

        status.automatic_waiting = True
        if not ready:
            channel.offline_samples = 0
            status.automatic_error = None
            return

        now = time.monotonic()
        if now - channel.last_attempt < AUTOMATIC_RETRY_SECONDS:
            return
        channel.last_attempt = now
        try:
            self._start(source, automatic=True)
        except RuntimeError as exc:
            status.automatic_error = str(exc)
