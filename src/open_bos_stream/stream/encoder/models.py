"""
Encoder Models
"""

from __future__ import annotations

from dataclasses import dataclass

from open_bos_stream.stream.encoder.options import (
    EncoderOption,
)

@dataclass(slots=True)
class EncoderInfo:

    codec: str

    name: str

    available: bool

    hardware: bool

    transcodes: bool

    options: list[EncoderOption]
