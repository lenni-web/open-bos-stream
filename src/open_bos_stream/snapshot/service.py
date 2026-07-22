"""
Snapshot Service
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from open_bos_stream.core.models import AppConfig


class SnapshotService:
    """Verwaltet Snapshots der Videoquelle."""

    def __init__(
        self,
        config: AppConfig,
        directory: str = "snapshots",
    ) -> None:

        self._config = config

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

    def next_filename(self) -> Path:
        """Nächsten Dateinamen erzeugen."""

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        return (
            self.directory
            / f"snapshot_{timestamp}.jpg"
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

        filename = self.next_filename()

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-rtsp_transport",
                "tcp",
                "-i",
                self._config.stream.rtsp_url,
                "-frames:v",
                "1",
                str(filename),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        self._last_snapshot = filename

        return filename
