"""
Recording models.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class RecordingStatus(BaseModel):
    """Aktueller Status einer Videoaufzeichnung."""

    recording: bool = False

    filename: str | None = None

    pid: int | None = None

    duration: int = 0

    started_at: float | None = None

    source_id: str | None = None

    source_name: str | None = None

    end_reason: str | None = None

    end_message: str | None = None

    completed_filename: str | None = None

    finished_at: float | None = None

    mode: Literal["manual", "automatic"] = "manual"

    automatic_waiting: bool = False

    automatic_error: str | None = None
