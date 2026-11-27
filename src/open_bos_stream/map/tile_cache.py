"""Dauerhafter Zwischenspeicher für Luftbildkacheln auf der Festplatte.

Eine Datei je Kachel (``Zoom/x/y.webp``). Die Änderungszeit ist der
Abrufzeitpunkt, die Zugriffszeit die letzte Nutzung; sie wird selbst
gesetzt, weil viele Systeme sie nicht mehr pflegen. Der Ordner darf
jederzeit gelöscht werden.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable


LOGGER = logging.getLogger(__name__)

# Aufnahmen haben Vorrang: Darunter wird nichts Neues gespeichert.
MIN_FREE_BYTES = 2 * 1024 ** 3
# Beim Aufräumen etwas Luft schaffen, damit nicht jede Kachel räumt.
PRUNE_TARGET = 0.9


class TileDiskCache:
    def __init__(
        self,
        directory: Path,
        max_bytes: int,
        *,
        min_free_bytes: int = MIN_FREE_BYTES,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.directory = Path(directory)
        self.max_bytes = max_bytes
        self.min_free_bytes = min_free_bytes
        self._clock = clock
        self._lock = threading.Lock()
        # Belegte Größe; erst beim ersten Schreiben ermittelt.
        self._size: int | None = None
        self._warned = False

    def _path(self, z: int, x: int, y: int) -> Path:
        return self.directory / str(int(z)) / str(int(x)) / f"{int(y)}.webp"

    def get(self, z: int, x: int, y: int) -> tuple[bytes, float] | None:
        """Gespeicherte Kachel und ihr Alter in Sekunden."""

        path = self._path(z, x, y)
        try:
            fetched = path.stat().st_mtime
            data = path.read_bytes()
        except OSError:
            return None
        if not data:
            return None
        now = self._clock()
        try:
            os.utime(path, (now, fetched))
        except OSError:
            pass
        return data, max(0.0, now - fetched)

    def put(self, z: int, x: int, y: int, data: bytes) -> None:
        """Kachel speichern; Fehler verhindern nie die Auslieferung."""

        path = self._path(z, x, y)
        try:
            with self._lock:
                path.parent.mkdir(parents=True, exist_ok=True)
                if shutil.disk_usage(path.parent).free < self.min_free_bytes:
                    return
                if self._size is None:
                    self._size = sum(size for _, size, _ in self._files())
                previous = path.stat().st_size if path.exists() else 0
                self._write(path, data)
                self._size += len(data) - previous
                if self._size > self.max_bytes:
                    self._prune()
        except OSError as exc:
            if not self._warned:
                self._warned = True
                LOGGER.warning("Luftbild-Zwischenspeicher nicht beschreibbar: %s", exc)

    def _write(self, path: Path, data: bytes) -> None:
        # Erst vollständig schreiben, dann umbenennen: nie halbe Kacheln.
        handle, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(handle, "wb") as file:
                file.write(data)
            now = self._clock()
            os.utime(temporary, (now, now))
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def _files(self) -> list[tuple[float, int, Path]]:
        files = []
        for path in self.directory.glob("*/*/*.webp"):
            try:
                stat = path.stat()
            except OSError:
                continue
            files.append((stat.st_atime, stat.st_size, path))
        return files

    def _prune(self) -> None:
        """Am längsten nicht genutzte Kacheln löschen."""

        files = sorted(self._files())
        size = sum(entry[1] for entry in files)
        for _, file_size, path in files:
            if size <= self.max_bytes * PRUNE_TARGET:
                break
            path.unlink(missing_ok=True)
            size -= file_size
        self._size = size
