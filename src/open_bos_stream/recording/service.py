"""
Recording Service
"""

from __future__ import annotations

import time
from threading import RLock

from open_bos_stream.core.models import AppConfig
from open_bos_stream.media.capture import CaptureInput, CaptureInputProvider
from open_bos_stream.media.storage import MediaStorageService
from open_bos_stream.mediamtx.client import MediaMTXClient
from open_bos_stream.recording.manager import RecordingManager
from open_bos_stream.recording.models import RecordingStatus
from open_bos_stream.recording.recorder import Recorder


class RecordingService:
    """Geschäftslogik für Videoaufzeichnungen."""

    def __init__(
        self,
        config: AppConfig,
        mediamtx: MediaMTXClient,
        storage: MediaStorageService | None = None,
        relays=None,
    ) -> None:

        self._config = config

        self._recorder = Recorder()

        self._manager = RecordingManager()

        self._status = RecordingStatus()

        self._mediamtx = mediamtx

        self._storage = storage

        self._capture = CaptureInputProvider(mediamtx, relays)

        self._capture_input: CaptureInput | None = None

        self._capture_renewed_at = 0.0

        self._control_lock = RLock()

        self._automatic_last_attempt = 0.0

        self._automatic_offline_samples = 0

    @property
    def status(self) -> RecordingStatus:
        """Aktuellen Aufnahmestatus zurückgeben."""

        self._status.recording = self._manager.running
        self._status.pid = self._manager.pid
        self._status.mode = self._config.media_capture.recording_mode
        self._status.automatic_waiting = (
            self._status.mode == "automatic"
            and not self._manager.running
        )

        outcome = getattr(self._manager, "last_outcome", None)
        if outcome is not None:
            self._status.end_reason = outcome.reason
            self._status.end_message = outcome.message
            self._status.completed_filename = outcome.filename
            self._status.finished_at = outcome.finished_at
            if not self._manager.running:
                self._status.started_at = None

        if (
            self._manager.running
            and self._status.started_at is not None
        ):
            self._status.duration = int(
                time.time() - self._status.started_at
            )

        return self._status

    def start(self, *, automatic: bool = False) -> None:
        """Aufnahme starten."""

        with self._control_lock:
            self._start(automatic=automatic)

    def _start(self, *, automatic: bool) -> None:
        if (
            self._config.media_capture.recording_mode == "automatic"
            and not automatic
        ):
            raise RuntimeError(
                "Die Aufnahme wird automatisch durch das Eingangssignal gesteuert."
            )

        if self._manager.running:
            return

        source = self._selected_source()
        path = self._mediamtx.path(source.viewer_path)

        if path is None:
            raise RuntimeError(
                f"Quelle '{source.name}' ist nicht verfügbar."
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
            self._manager.start(
                filename,
                capture.url,
                transcode_video=not (h264 or hevc),
                transcode_audio=not browser_audio,
                hevc=hevc and not h264,
            )
        except Exception:
            self._capture.release(capture)
            raise

        self._capture_input = capture
        self._capture_renewed_at = time.monotonic()
        self._status.full_quality = capture.full_quality

        self._status.filename = str(filename)
        self._status.started_at = time.time()
        self._status.duration = 0
        self._status.recording = True
        self._status.pid = self._manager.pid
        self._status.source_id = source.id
        self._status.source_name = source.name
        self._status.end_reason = None
        self._status.end_message = None
        self._status.completed_filename = None
        self._status.finished_at = None
        self._status.automatic_error = None
        self._status.automatic_waiting = False

    def stop(self, *, automatic: bool = False) -> None:
        """Aufnahme stoppen."""

        with self._control_lock:
            self._stop(automatic=automatic)

    def _stop(self, *, automatic: bool) -> None:
        if (
            self._config.media_capture.recording_mode == "automatic"
            and not automatic
        ):
            raise RuntimeError(
                "Die Aufnahme wird automatisch durch das Eingangssignal gesteuert."
            )

        try:
            self._manager.stop()
        finally:
            self._release_capture()
            self._status.recording = False
            self._status.started_at = None
            self._status.duration = 0
            self._status.pid = None

    def stop_for_storage(self, message: str) -> None:
        """Laufende Aufnahme wegen Speichermangel sauber abschließen."""

        with self._control_lock:
            if not self._manager.running:
                return
            try:
                self._manager.stop(reason="storage_low", message=message)
            finally:
                self._release_capture()
                self._status.recording = False
                self._status.started_at = None
                self._status.duration = 0
                self._status.pid = None

    def maintain(self) -> None:
        """Periodische Pflege: Hauptstream halten und Automatik abgleichen."""

        with self._control_lock:
            self._maintain_capture()
        self.reconcile_automatic()

    def _maintain_capture(self) -> None:
        if self._capture_input is None:
            return
        if not self._manager.running:
            # Aufnahme wurde ohne Bedienaktion beendet (z. B. Streamabbruch).
            self._release_capture()
            return
        now = time.monotonic()
        if now - self._capture_renewed_at >= 10:
            self._capture.renew(self._capture_input)
            self._capture_renewed_at = now

    def _release_capture(self) -> None:
        self._capture.release(self._capture_input)
        self._capture_input = None
        self._status.full_quality = None

    def reconcile_automatic(self) -> None:
        """Aufnahmezustand an das Signal der gewählten Quelle angleichen."""

        with self._control_lock:
            if self._config.media_capture.recording_mode != "automatic":
                self._automatic_offline_samples = 0
                self._status.automatic_waiting = False
                self._status.automatic_error = None
                return

            self._status.mode = "automatic"
            try:
                source = self._selected_source()
            except RuntimeError as exc:
                self._status.automatic_waiting = True
                self._status.automatic_error = str(exc)
                return

            path = self._mediamtx.path(source.viewer_path)
            ready = bool(path and path.get("ready", False))

            if self._manager.running:
                if self._status.source_id != source.id:
                    self._stop(automatic=True)
                    self._automatic_offline_samples = 0
                    return
                if ready:
                    self._automatic_offline_samples = 0
                    self._status.automatic_error = None
                    return
                self._automatic_offline_samples += 1
                if self._automatic_offline_samples >= 2:
                    self._stop(automatic=True)
                    self._automatic_offline_samples = 0
                return

            self._status.automatic_waiting = True
            if not ready:
                self._automatic_offline_samples = 0
                self._status.automatic_error = None
                return

            now = time.monotonic()
            if now - self._automatic_last_attempt < 5:
                return
            self._automatic_last_attempt = now
            try:
                self._start(automatic=True)
            except RuntimeError as exc:
                self._status.automatic_error = str(exc)

    def _selected_source(self):
        selected_id = self._config.media_capture.source_id
        source = next(
            (
                item
                for item in self._config.sources
                if item.enabled and item.id == selected_id
            ),
            None,
        )
        if source is None:
            source = next(
                (item for item in self._config.sources if item.enabled),
                None,
            )
        if source is None:
            raise RuntimeError("Keine aktive Medienquelle konfiguriert.")
        return source
