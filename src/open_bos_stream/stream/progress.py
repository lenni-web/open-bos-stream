"""Kompakte Auswertung des maschinenlesbaren FFmpeg-Fortschritts."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class FFmpegProgress:
    """Merkt nur echten Medienfortschritt, nicht bloße Prozessausgabe."""

    frame: int = 0
    out_time_us: int = 0
    fps: float = 0.0
    speed: float = 0.0
    dropped_frames: int = 0
    duplicated_frames: int = 0
    last_advance: float | None = None
    _block: dict[str, str] = field(default_factory=dict, repr=False)

    def feed(self, line: str, *, now: float | None = None) -> bool:
        """Verarbeitet eine ``-progress``-Zeile und meldet Fortschritt."""

        key, separator, value = line.strip().partition("=")
        if not separator:
            return False

        self._block[key] = value
        if key != "progress":
            return False

        previous = (self.frame, self.out_time_us)
        self.frame = self._integer("frame", self.frame)
        self.out_time_us = self._integer(
            "out_time_us",
            self._integer("out_time_ms", self.out_time_us),
        )
        self.fps = self._number("fps", self.fps)
        self.speed = self._number(
            "speed",
            self.speed,
            suffix="x",
        )
        self.dropped_frames = self._integer(
            "drop_frames",
            self.dropped_frames,
        )
        self.duplicated_frames = self._integer(
            "dup_frames",
            self.duplicated_frames,
        )
        self._block.clear()

        advanced = (
            self.frame > previous[0]
            or self.out_time_us > previous[1]
        )
        if advanced:
            self.last_advance = time.monotonic() if now is None else now
        return advanced

    def stale(
        self,
        *,
        now: float,
        started_at: float,
        startup_grace: float,
        timeout: float,
    ) -> bool:
        reference = self.last_advance
        if reference is None:
            return now - started_at > startup_grace
        return now - reference > timeout

    def _integer(self, key: str, fallback: int) -> int:
        try:
            return int(self._block.get(key, fallback))
        except (TypeError, ValueError):
            return fallback

    def _number(
        self,
        key: str,
        fallback: float,
        *,
        suffix: str = "",
    ) -> float:
        value = self._block.get(key)
        if value is None:
            return fallback
        if suffix and value.endswith(suffix):
            value = value[:-len(suffix)]
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback
