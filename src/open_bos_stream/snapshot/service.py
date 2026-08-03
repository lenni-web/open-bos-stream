"""
Snapshot Service
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from open_bos_stream.core.models import AppConfig
from open_bos_stream.core.process import ProcessRunner
from open_bos_stream.mediamtx.client import MediaMTXClient


class SnapshotService:
    """Verwaltet Snapshots der Videoquelle."""

    def __init__(
        self,
        config: AppConfig,
        mediamtx: MediaMTXClient,
        directory: str = "snapshots",
        runner: ProcessRunner | None = None,
    ) -> None:

        self._config = config
        self._runner = runner or ProcessRunner()
        self._mediamtx = mediamtx

        self.directory = Path(directory)
        self.directory.mkdir(exist_ok=True)

        self._last_snapshot: Path | None = None

    @property
    def last_snapshot(self) -> Path | None:
        """Letzten Snapshot zurückgeben."""

        if self._last_snapshot is not None:
            return self._last_snapshot

        return self.latest_snapshot()

    @property
    def count(self) -> int:
        """Anzahl aller Snapshots."""

        return len(
            list(
                self.directory.glob("snapshot_*.jpg")
            )
        )

    @property
    def status(self) -> dict:
        """Status für API und Dashboard."""

        snapshot = self.last_snapshot

        return {
            "last_snapshot": (
                snapshot.name
                if snapshot is not None
                else None
            ),
            "count": self.count,
        }

    def next_filename(self, source_id: str) -> Path:
        """Nächsten Dateinamen erzeugen."""

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        return (
            self.directory
            / f"snapshot_{source_id}_{timestamp}.jpg"
        )

    def latest_snapshot(self) -> Path | None:
        """Neuesten Snapshot suchen."""

        files = sorted(
            self.directory.glob("snapshot_*.jpg"),
            reverse=True,
        )

        if not files:
            return None

        return files[0]

    def create(self) -> Path:
        """Neuen Snapshot erzeugen."""

        source = self._selected_source()
        path = self._mediamtx.path(source.viewer_path)
        if path is None or not path.get("ready", False):
            raise RuntimeError(
                f"Quelle '{source.name}' ist nicht verfügbar."
            )
        filename = self.next_filename(source.id)
        working_file = filename.with_name(f".{filename.name}.part")
        working_file.unlink(missing_ok=True)

        try:
            self._runner.run(
                [
                    "ffmpeg",
                    "-y",
                    "-rtsp_transport",
                    "tcp",
                    "-fflags",
                    "+genpts+discardcorrupt",
                    "-err_detect",
                    "ignore_err",
                    # Nicht den ersten beliebigen, eventuell nur grau
                    # rekonstruierten HEVC-Frame verwenden. Auf einen
                    # vollständigen Schlüsselbild-Frame warten.
                    "-skip_frame",
                    "nokey",
                    "-i",
                    f"rtsp://127.0.0.1:8554/{source.viewer_path}",
                    "-an",
                    "-frames:v",
                    "1",
                    "-q:v",
                    "2",
                    "-update",
                    "1",
                    "-f",
                    "image2",
                    str(working_file),
                ],
                timeout=20,
                check=True,
            )

            if (
                not working_file.exists()
                or working_file.stat().st_size < 1024
            ):
                raise RuntimeError(
                    "FFmpeg hat keinen vollständigen Snapshot erzeugt."
                )

            working_file.replace(filename)
        except Exception:
            working_file.unlink(missing_ok=True)
            raise

        self._last_snapshot = filename

        return filename

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
