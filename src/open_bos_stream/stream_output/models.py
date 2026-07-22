"""
Streaming Output Models
"""

from __future__ import annotations

from pydantic import BaseModel


class StreamOutputStatus(BaseModel):
    """Aktueller Status eines Streaming Outputs."""

    name: str

    enabled: bool

    running: bool = False

    pid: int | None = None
