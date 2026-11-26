"""
Encoder Option Model
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)


@dataclass(slots=True)
class EncoderOption:

    id: str

    label: str

    type: str = "text"

    default: str = ""

    choices: list[str] = field(
        default_factory=list,
    )

    placeholder: str = ""

    description: str = ""

    required: bool = False

    ffmpeg: str = ""

    ffmpeg_filter: str = ""