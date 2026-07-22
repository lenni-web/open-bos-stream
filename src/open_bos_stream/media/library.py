"""
Media Library
"""

from __future__ import annotations

from typing import TypedDict

from open_bos_stream.recording.library import RecordingLibrary
from open_bos_stream.snapshot.library import SnapshotLibrary


class MediaItem(TypedDict):

    type: str
    name: str
    size: int
    modified: float


class MediaLibrary:
    """Gemeinsame Mediathek."""

    def __init__(
        self,
        recordings: RecordingLibrary,
        snapshots: SnapshotLibrary,
    ) -> None:

        self._recordings = recordings
        self._snapshots = snapshots

    def list(self) -> list[MediaItem]:

        files: list[MediaItem] = []

        files.extend(
            self._recordings.list()
        )

        files.extend(
            self._snapshots.list()
        )

        files.sort(
            key=lambda item: item["modified"],
            reverse=True,
        )

        return files
