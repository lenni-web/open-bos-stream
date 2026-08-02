"""
Recording Service
"""

from __future__ import annotations

import time

from open_bos_stream.core.models import AppConfig
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
    ) -> None:

        self._config = config

        self._recorder = Recorder()

        self._manager = RecordingManager()

        self._status = RecordingStatus()

        self._mediamtx = mediamtx

    @property
    def status(self) -> RecordingStatus:
        """Aktuellen Aufnahmestatus zurückgeben."""

        self._status.recording = self._manager.running
        self._status.pid = self._manager.pid

        if (
            self._manager.running
            and self._status.started_at is not None
        ):
            self._status.duration = int(
                time.time() - self._status.started_at
            )

        return self._status

    def start(self) -> None:
        """Aufnahme starten."""

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

        filename = self._recorder.next_filename(source.id)
        input_url = f"rtsp://127.0.0.1:8554/{source.viewer_path}"

        tracks = [str(item).lower() for item in path.get("tracks", [])]
        video_codec = str(path.get("codec") or "").lower()
        browser_video = video_codec in {"h264", "avc"} or any(
            "h264" in item for item in tracks
        )
        audio_tracks = [
            item for item in tracks
            if not any(video in item for video in ("h264", "h265", "avc", "hevc"))
        ]
        browser_audio = not audio_tracks or any(
            "aac" in item or "mpeg-4 audio" in item
            for item in audio_tracks
        )

        self._manager.start(
            filename,
            input_url,
            transcode_video=not browser_video,
            transcode_audio=not browser_audio,
        )

        self._status.filename = str(filename)
        self._status.started_at = time.time()
        self._status.duration = 0
        self._status.recording = True
        self._status.pid = self._manager.pid
        self._status.source_id = source.id
        self._status.source_name = source.name

    def stop(self) -> None:
        """Aufnahme stoppen."""

        try:
            self._manager.stop()
        finally:
            self._status.recording = False
            self._status.started_at = None
            self._status.duration = 0
            self._status.pid = None

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
