"""Speicherinformationen für lokale Medien."""

from __future__ import annotations

import shutil
from pathlib import Path


class MediaStorageService:
    def __init__(
        self,
        recordings: str = "recordings",
        snapshots: str = "snapshots",
    ) -> None:
        self._recordings = Path(recordings)
        self._snapshots = Path(snapshots)

    @staticmethod
    def _directory_size(directory: Path) -> tuple[int, int]:
        if not directory.exists():
            return 0, 0

        files = [
            path
            for path in directory.iterdir()
            if path.is_file()
        ]
        return len(files), sum(path.stat().st_size for path in files)

    def status(self) -> dict:
        base = self._recordings.resolve().parent
        usage = shutil.disk_usage(base)
        recording_count, recording_bytes = self._directory_size(
            self._recordings
        )
        snapshot_count, snapshot_bytes = self._directory_size(
            self._snapshots
        )

        return {
            "path": str(base),
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "used_percent": (
                usage.used / usage.total * 100
                if usage.total
                else 0
            ),
            "media_bytes": recording_bytes + snapshot_bytes,
            "recordings": recording_count,
            "snapshots": snapshot_count,
        }
