"""
Recording Library
"""

from __future__ import annotations

from open_bos_stream.core.file_library import (
    FileLibrary,
)


class RecordingLibrary(FileLibrary):
    """Verwaltet gespeicherte Videoaufzeichnungen."""

    extension = ".mp4"

    media_type = "recording"

    def __init__(
        self,
        directory: str = "recordings",
    ) -> None:

        super().__init__(directory)