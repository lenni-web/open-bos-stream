"""
Snapshot Library
"""

from __future__ import annotations

from open_bos_stream.core.file_library import (
    FileLibrary,
)


class SnapshotLibrary(FileLibrary):
    """Verwaltet gespeicherte Snapshots."""

    extension = ".jpg"

    media_type = "snapshot"

    def __init__(
        self,
        directory: str = "snapshots",
    ) -> None:

        super().__init__(directory)