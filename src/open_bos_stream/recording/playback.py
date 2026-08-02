"""Browserkompatibler Wiedergabe-Cache für Aufnahmen."""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path


class PlaybackPreparationError(RuntimeError):
    pass


class RecordingPlaybackCache:
    def __init__(self, directory: Path) -> None:
        self._directory = directory / ".playback-cache"
        self._lock = threading.Lock()

    def prepare(self, source: Path) -> Path:
        stat = source.stat()
        target = self._directory / (
            f"{source.stem}-{stat.st_size}-{stat.st_mtime_ns}.mp4"
        )
        with self._lock:
            self._directory.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.stat().st_size > 0:
                return target
            temporary = target.with_suffix(".part")
            command = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error",
                "-nostdin",
                "-y",
                "-i", str(source),
                "-map", "0:v:0",
                "-map", "0:a:0?",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-movflags", "+faststart",
                "-f", "mp4",
                str(temporary),
            ]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0 or not temporary.exists():
                temporary.unlink(missing_ok=True)
                detail = completed.stderr.strip()
                raise PlaybackPreparationError(
                    detail or "FFmpeg konnte die Aufnahme nicht konvertieren."
                )
            temporary.replace(target)
            self._remove_stale(source, keep=target)
            return target

    def remove(self, source: Path) -> None:
        with self._lock:
            if not self._directory.exists():
                return
            for item in self._directory.glob(f"{source.stem}-*.mp4"):
                item.unlink(missing_ok=True)

    def _remove_stale(self, source: Path, *, keep: Path) -> None:
        for item in self._directory.glob(f"{source.stem}-*.mp4"):
            if item != keep:
                item.unlink(missing_ok=True)
