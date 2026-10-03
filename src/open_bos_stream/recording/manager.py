"""
Recording Manager

Zentrale Steuerung der Videoaufzeichnung.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging
import subprocess
import threading
import time
from pathlib import Path

from open_bos_stream.recording.command import RecordingCommandBuilder
from open_bos_stream.recording.process import RecordingProcess


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecordingOutcome:
    reason: str
    message: str
    filename: str | None
    finished_at: float


class RecordingManager:

    def __init__(self) -> None:

        self._builder = RecordingCommandBuilder()

        self._process = RecordingProcess()

        self._final_file: Path | None = None

        self._working_file: Path | None = None

        self._lock = threading.RLock()

        self._generation = 0

        self._last_outcome: RecordingOutcome | None = None

    @property
    def running(self) -> bool:

        return self._process.running

    @property
    def pid(self) -> int | None:

        return self._process.pid

    @property
    def last_outcome(self) -> RecordingOutcome | None:
        with self._lock:
            return self._last_outcome

    def start(
        self,
        filename: Path,
        input_url: str,
        *,
        transcode_video: bool = False,
        transcode_audio: bool = False,
    ) -> bool:

        with self._lock:
            if self.running:
                return True

            # Ein unerwartet beendeter Vorgänger wird vor einer neuen
            # Aufnahme noch abgeschlossen, selbst wenn der Wächter noch
            # nicht zum Zug gekommen ist.
            if self._working_file is not None:
                try:
                    self._finalize_locked(unexpected=True)
                except RuntimeError:
                    logger.exception(
                        "Unerwartet beendete Aufnahme war nicht verwertbar."
                    )

            working_file = filename.with_name(f".{filename.name}.part")
            working_file.unlink(missing_ok=True)
            command = self._builder.build(
                working_file,
                input_url,
                transcode_video=transcode_video,
                transcode_audio=transcode_audio,
            )

            try:
                self._process.start(command)
            except Exception:
                working_file.unlink(missing_ok=True)
                raise

            self._final_file = filename
            self._working_file = working_file
            self._last_outcome = None
            self._generation += 1
            generation = self._generation

            threading.Thread(
                target=self._watch_process,
                args=(generation,),
                name="open-bos-recording-watch",
                daemon=True,
            ).start()

        return self.running

    def stop(
        self,
        *,
        reason: str | None = None,
        message: str | None = None,
    ) -> bool:
        with self._lock:
            self._generation += 1
            if self._working_file is None or self._final_file is None:
                return True
            self._finalize_locked(unexpected=False)
            if (
                reason is not None
                and self._last_outcome is not None
                and self._last_outcome.reason == "completed"
            ):
                self._last_outcome = replace(
                    self._last_outcome,
                    reason=reason,
                    message=message or self._last_outcome.message,
                )
            return True

    def _watch_process(self, generation: int) -> None:
        """Schließt eine ohne Bedienaktion beendete Aufnahme automatisch ab."""

        while True:
            time.sleep(0.25)
            with self._lock:
                if generation != self._generation:
                    return
                if self._process.running:
                    continue
                try:
                    self._finalize_locked(unexpected=True)
                except RuntimeError:
                    logger.exception(
                        "Aufnahme endete unerwartet und konnte nicht "
                        "veröffentlicht werden."
                    )
                return

    def _finalize_locked(self, *, unexpected: bool) -> None:
        """Validiert und veröffentlicht eine Aufnahme unter gehaltenem Lock."""

        returncode = self._process.stop()
        working_file = self._working_file
        final_file = self._final_file
        self._working_file = None
        self._final_file = None

        try:
            # FFmpeg kann nach einem kontrollierten SIGINT einen Nicht-Null-
            # Code liefern, obwohl der MP4-Trailer korrekt geschrieben wurde.
            # Entscheidend ist deshalb die validierte Datei, nicht allein der
            # Prozesscode oder tolerierbare Decoderwarnungen der Quelle.
            self._validate(working_file)
        except RuntimeError as exc:
            detail = self._process.last_error or f"Exit {returncode}"
            message = (
                "Aufnahme endete unerwartet und enthält keine gültige "
                f"MP4-Datei: {exc}"
            )
            self._last_outcome = RecordingOutcome(
                reason="failed",
                message=message,
                filename=None,
                finished_at=time.time(),
            )
            raise RuntimeError(
                "Aufnahme konnte nicht als gültige MP4-Datei abgeschlossen "
                f"werden: {exc}\nFFmpeg: {detail}"
            ) from exc

        working_file.replace(final_file)
        self._last_outcome = RecordingOutcome(
            reason=("stream_interrupted" if unexpected else "completed"),
            message=(
                "Streamverbindung wurde unterbrochen. Die bis dahin "
                "aufgezeichneten Videodaten wurden gespeichert."
                if unexpected
                else "Aufnahme wurde abgeschlossen."
            ),
            filename=str(final_file),
            finished_at=time.time(),
        )

    @staticmethod
    def _validate(file: Path) -> None:
        if not file.exists() or file.stat().st_size == 0:
            file.unlink(missing_ok=True)
            raise RuntimeError("Aufnahme enthält keine Videodaten.")
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=codec_type",
                    "-of", "csv=p=0",
                    str(file),
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            file.unlink(missing_ok=True)
            raise RuntimeError(
                f"Aufnahme konnte nicht validiert werden: {exc}"
            ) from exc
        if result.returncode != 0 or "video" not in result.stdout.lower():
            detail = result.stderr.strip()
            file.unlink(missing_ok=True)
            raise RuntimeError(
                "Aufnahme ist keine gültige MP4-Videodatei"
                + (f": {detail}" if detail else ".")
            )
