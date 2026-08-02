"""Flüchtiger Statuskanal zwischen Streamer und Webanwendung."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Mapping


DEFAULT_STATUS_FILE = Path(
    "/run/open-bos-stream/ffmpeg-progress.json"
)


class StreamRuntimeStatusStore:
    """Schreibt kleine Status-Snapshots atomar in das Runtime-Verzeichnis."""

    def __init__(self, path: Path = DEFAULT_STATUS_FILE) -> None:
        self._path = path

    def write(self, sources: Mapping[str, Mapping[str, Any]]) -> None:
        payload = {
            "updated_at": time.time(),
            "sources": sources,
        }
        temporary = self._path.with_suffix(".tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(payload, separators=(",", ":")),
                encoding="utf-8",
            )
            os.replace(temporary, self._path)
        except OSError:
            # Diagnose darf den eigentlichen Stream niemals beenden.
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def read(self, *, max_age: float = 5.0) -> dict[str, dict[str, Any]]:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            updated_at = float(payload.get("updated_at", 0))
            sources = payload.get("sources", {})
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {}

        if time.time() - updated_at > max_age or not isinstance(sources, dict):
            return {}
        return {
            str(source_id): dict(status)
            for source_id, status in sources.items()
            if isinstance(status, dict)
        }

    def clear(self) -> None:
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            pass
