"""
V4L2 Device Model
"""

from __future__ import annotations

from dataclasses import dataclass, field

from open_bos_stream.stream.video_formats import (
    VideoFormat,
)


@dataclass(slots=True)
class V4L2Device:

    path: str

    name: str

    driver: str = ""

    bus: str = ""

    capabilities: list[str] = field(
        default_factory=list,
    )

    formats: list[VideoFormat] = field(
        default_factory=list,
    )