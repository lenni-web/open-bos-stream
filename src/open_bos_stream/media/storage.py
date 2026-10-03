"""Speicherinformationen, Speicherschutz und Bereinigung lokaler Medien."""

from __future__ import annotations

import logging
import shutil
import threading
import time
from pathlib import Path
from typing import Callable

from open_bos_stream.core.models import StorageConfig
from open_bos_stream.recording.library import RecordingLibrary
from open_bos_stream.recording.playback import RecordingPlaybackCache
from open_bos_stream.snapshot.library import SnapshotLibrary


logger = logging.getLogger(__name__)

# Die Bereinigung gibt etwas mehr als die Mindestgrenze frei, damit sie
# nicht bei jeder neuen Datei erneut einzelne Medien löscht.
CLEANUP_MARGIN_PERCENT = 2


class StorageFullError(RuntimeError):
    """Neue Medien können wegen zu wenig freiem Speicher nicht entstehen."""


class MediaStorageService:
    def __init__(
        self,
        recordings: str = "recordings",
        snapshots: str = "snapshots",
        *,
        config=None,
        recording_library: RecordingLibrary | None = None,
        snapshot_library: SnapshotLibrary | None = None,
        playback_cache: RecordingPlaybackCache | None = None,
        disk_usage: Callable = shutil.disk_usage,
    ) -> None:
        self._recordings = Path(recordings)
        self._snapshots = Path(snapshots)
        self._config = config
        self._recording_library = recording_library
        self._snapshot_library = snapshot_library
        self._playback_cache = playback_cache
        self._disk_usage = disk_usage
        self._lock = threading.Lock()
        self._last_cleanup: dict | None = None
        self._last_level = "ok"

    # -----------------------------------------------------
    # Schwellwerte
    # -----------------------------------------------------

    @property
    def settings(self) -> StorageConfig:
        storage = getattr(self._config, "storage", None)
        return storage if storage is not None else StorageConfig()

    def _base(self) -> Path:
        return self._recordings.resolve().parent

    def free_percent(self) -> float:
        usage = self._disk_usage(self._base())
        if not usage.total:
            return 100.0
        return usage.free / usage.total * 100

    def level(self, free_percent: float | None = None) -> str:
        free = self.free_percent() if free_percent is None else free_percent
        settings = self.settings
        if free < settings.minimum_free_percent:
            return "critical"
        if free < settings.warning_free_percent:
            return "warning"
        return "ok"

    def blocked_message(self, free_percent: float | None = None) -> str:
        free = self.free_percent() if free_percent is None else free_percent
        settings = self.settings
        message = (
            f"Zu wenig freier Speicher ({free:.1f} % frei, Mindestgrenze "
            f"{settings.minimum_free_percent} %). Neue Aufnahmen und "
            "Snapshots sind gesperrt."
        )
        if settings.auto_cleanup:
            message += (
                " Die automatische Bereinigung konnte nicht genug Speicher "
                "freigeben; die übrigen Medien sind als „Behalten“ markiert."
            )
        else:
            message += (
                " Bitte Medien löschen oder die automatische Bereinigung "
                "aktivieren."
            )
        return message

    # -----------------------------------------------------
    # Status
    # -----------------------------------------------------

    @staticmethod
    def _directory_size(directory: Path) -> tuple[int, int]:
        if not directory.exists():
            return 0, 0

        files = [
            path
            for path in directory.iterdir()
            if path.is_file() and not path.name.startswith(".")
        ]
        return len(files), sum(path.stat().st_size for path in files)

    def status(self) -> dict:
        base = self._base()
        usage = self._disk_usage(base)
        recording_count, recording_bytes = self._directory_size(
            self._recordings
        )
        snapshot_count, snapshot_bytes = self._directory_size(
            self._snapshots
        )
        free_percent = (
            usage.free / usage.total * 100
            if usage.total
            else 100.0
        )
        level = self.level(free_percent)
        settings = self.settings

        return {
            "path": str(base),
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "used_percent": (
                usage.used / usage.total * 100
                if usage.total
                else 0
            ),
            "free_percent": free_percent,
            "level": level,
            "blocked": level == "critical",
            "blocked_message": (
                self.blocked_message(free_percent)
                if level == "critical"
                else None
            ),
            "warning_free_percent": settings.warning_free_percent,
            "minimum_free_percent": settings.minimum_free_percent,
            "auto_cleanup": settings.auto_cleanup,
            "last_cleanup": self._last_cleanup,
            "media_bytes": recording_bytes + snapshot_bytes,
            "recordings": recording_count,
            "snapshots": snapshot_count,
        }

    # -----------------------------------------------------
    # Speicherschutz
    # -----------------------------------------------------

    def ensure_capacity(self) -> None:
        """Vor neuen Medien prüfen; bei Bedarf bereinigen oder sperren."""

        free = self.free_percent()
        settings = self.settings
        if free >= settings.minimum_free_percent:
            return
        if settings.auto_cleanup:
            self.cleanup()
            free = self.free_percent()
            if free >= settings.minimum_free_percent:
                return
        raise StorageFullError(self.blocked_message(free))

    def enforce(self) -> bool:
        """Periodische Prüfung. Liefert False, solange Medien gesperrt sind."""

        free = self.free_percent()
        settings = self.settings
        if (
            free < settings.minimum_free_percent
            and settings.auto_cleanup
        ):
            self.cleanup()
            free = self.free_percent()

        level = self.level(free)
        if level != self._last_level:
            if level == "critical":
                logger.warning(
                    "Speicher kritisch: %.1f %% frei (Mindestgrenze %s %%).",
                    free,
                    settings.minimum_free_percent,
                )
            elif level == "warning":
                logger.warning(
                    "Speicher wird knapp: %.1f %% frei (Warnschwelle %s %%).",
                    free,
                    settings.warning_free_percent,
                )
            else:
                logger.info("Speicher wieder ausreichend: %.1f %% frei.", free)
            self._last_level = level

        return level != "critical"

    def cleanup(self) -> list[str]:
        """Älteste nicht geschützte Medien löschen, bis genug frei ist."""

        settings = self.settings
        target = min(
            settings.minimum_free_percent + CLEANUP_MARGIN_PERCENT,
            settings.warning_free_percent,
        )
        deleted: list[str] = []
        freed = 0

        with self._lock:
            for library, file in self._cleanup_candidates():
                if self.free_percent() >= target:
                    break
                try:
                    size = file.stat().st_size
                except OSError:
                    continue
                if not library.delete(file.name):
                    continue
                if (
                    isinstance(library, RecordingLibrary)
                    and self._playback_cache is not None
                ):
                    self._playback_cache.remove(file)
                deleted.append(file.name)
                freed += size
                logger.warning(
                    "Automatische Speicherbereinigung: %s gelöscht "
                    "(%.1f %% frei).",
                    file.name,
                    self.free_percent(),
                )

            if deleted:
                self._last_cleanup = {
                    "at": time.time(),
                    "deleted": len(deleted),
                    "freed_bytes": freed,
                }

        return deleted

    def _libraries(self) -> list:
        if self._recording_library is None:
            self._recording_library = RecordingLibrary(str(self._recordings))
        if self._snapshot_library is None:
            self._snapshot_library = SnapshotLibrary(str(self._snapshots))
        return [self._recording_library, self._snapshot_library]

    def _cleanup_candidates(self) -> list[tuple[object, Path]]:
        candidates = []
        for library in self._libraries():
            for item in library.list():
                if item.get("protected"):
                    continue
                file = library.get_file(item["name"])
                if file is not None:
                    candidates.append((item["modified"], library, file))
        candidates.sort(key=lambda candidate: candidate[0])
        return [(library, file) for _, library, file in candidates]
