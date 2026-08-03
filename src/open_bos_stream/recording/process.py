"""
Recording FFmpeg process wrapper.

Verwaltet den Lebenszyklus eines FFmpeg-Aufnahmeprozesses.
"""

from __future__ import annotations

import logging
import signal
import subprocess
import tempfile
import time
from typing import TextIO

logger = logging.getLogger(__name__)


class RecordingProcess:
    """Verwaltet einen FFmpeg-Aufnahmeprozess."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._stderr_file: TextIO | None = None
        self.last_error = ""

    def _read_stderr(self) -> str:
        if self._stderr_file is None:
            return ""
        self._stderr_file.flush()
        self._stderr_file.seek(0)
        return self._stderr_file.read().strip()

    def _close_stderr(self) -> None:
        if self._stderr_file is not None:
            self._stderr_file.close()
            self._stderr_file = None

    @property
    def running(self) -> bool:
        """True, wenn der Prozess aktuell läuft."""
        return (
            self._process is not None
            and self._process.poll() is None
        )

    @property
    def pid(self) -> int | None:
        """PID des laufenden Prozesses."""
        if self._process is None:
            return None

        return self._process.pid

    def start(self, command: list[str]) -> None:
        """Startet den FFmpeg-Aufnahmeprozess."""

        if self.running:
            logger.warning("Recording läuft bereits.")
            return

        logger.info("Starting recording process")
        logger.info("Recording command: %s", " ".join(command))

        try:

            # Ein normales PIPE kann volllaufen, wenn eine beschädigte HEVC-
            # Quelle sehr viele Decoderwarnungen erzeugt. Eine temporäre Datei
            # hält FFmpeg auch in diesem Fall dauerhaft schreibfähig.
            self._close_stderr()
            self._stderr_file = tempfile.TemporaryFile(
                mode="w+t",
                encoding="utf-8",
            )

            self._process = subprocess.Popen(
                [
                    command[0],
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-nostats",
                    *command[1:],
                ],
                stdout=subprocess.DEVNULL,
                stderr=self._stderr_file,
                text=True,
            )

            # Kurz warten, damit FFmpeg sofortige Fehler melden kann.
            time.sleep(0.5)

            if self._process.poll() is not None:

                error = self._read_stderr()

                self._close_stderr()

                raise RuntimeError(
                    f"FFmpeg konnte die Aufnahme nicht starten:\n{error}"
                )

        except FileNotFoundError as exc:
            self._close_stderr()
            raise RuntimeError(
                "FFmpeg wurde nicht gefunden."
            ) from exc

        except Exception as exc:
            self._close_stderr()
            raise RuntimeError(
                f"Recording konnte nicht gestartet werden: {exc}"
            ) from exc

    def stop(self) -> int:
        """Beendet FFmpeg kontrolliert und liefert dessen Exit-Code."""

        if self._process is None:
            return 0

        logger.info("Stopping recording process")

        if self._process.poll() is None:
            self._process.send_signal(signal.SIGINT)

        try:
            self._process.wait(timeout=15)

        except subprocess.TimeoutExpired:

            logger.warning(
                "Recording reagiert nicht, Prozess wird beendet."
            )

            self._process.kill()
            self._process.wait()

        returncode = int(self._process.returncode or 0)
        self.last_error = self._read_stderr()
        self._close_stderr()
        self._process = None
        return returncode
