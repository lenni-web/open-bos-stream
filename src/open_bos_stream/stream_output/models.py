"""
Streaming Output Models
"""

from __future__ import annotations

from pydantic import BaseModel


class StreamOutputStatus(BaseModel):
    """Aktueller Status eines Streaming Outputs."""

    name: str

    source_id: str | None = None

    source_name: str | None = None

    enabled: bool

    running: bool = False

    pid: int | None = None

    error: str | None = None
