"""
Recording FFmpeg process wrapper.

Verwaltet den Lebenszyklus eines FFmpeg-Aufnahmeprozesses.
"""

from __future__ import annotations

import logging
import signal
import subprocess
import time

logger = logging.getLogger(__name__)


class RecordingProcess:
    """Verwaltet einen FFmpeg-Aufnahmeprozess."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self.last_error = ""

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
                stderr=subprocess.PIPE,
                text=True,
            )

            # Kurz warten, damit FFmpeg sofortige Fehler melden kann.
            time.sleep(0.5)

            if self._process.poll() is not None:

                error = self._process.stderr.read().strip()

                raise RuntimeError(
                    f"FFmpeg konnte die Aufnahme nicht starten:\n{error}"
                )

        except FileNotFoundError as exc:
            raise RuntimeError(
                "FFmpeg wurde nicht gefunden."
            ) from exc

        except Exception as exc:
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
            _, stderr = self._process.communicate(timeout=10)

        except subprocess.TimeoutExpired:

            logger.warning(
                "Recording reagiert nicht, Prozess wird beendet."
            )

            self._process.kill()
            _, stderr = self._process.communicate()

        returncode = int(self._process.returncode or 0)
        self.last_error = (stderr or "").strip()
        self._process = None
        return returncode
