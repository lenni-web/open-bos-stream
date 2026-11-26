"""
API-Modelle
"""

from __future__ import annotations

from pydantic import BaseModel


class EncoderRequest(
    BaseModel,
):
    type: str

    format: str | None = None

    mode: str | None = None

    url: str | None = None

    device: str | None = None

    width: int | None = None

    height: int | None = None

    fps: int | None = None
