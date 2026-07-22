"""
Recording models.
"""

from __future__ import annotations

from pydantic import BaseModel


class RecordingStatus(BaseModel):
    """Aktueller Status einer Videoaufzeichnung."""

    recording: bool = False

    filename: str | None = None

    pid: int | None = None

    duration: int = 0

    started_at: float | None = None
