"""
Recording FFmpeg process wrapper.

Verwaltet den Lebenszyklus eines FFmpeg-Aufnahmeprozesses.
"""

from __future__ import annotations

import logging
import subprocess
import time

logger = logging.getLogger(__name__)


class RecordingProcess:
    """Verwaltet einen FFmpeg-Aufnahmeprozess."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None

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
                command,
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

    def stop(self) -> None:
        """Beendet den Aufnahmeprozess."""

        if not self.running:
            return

        logger.info("Stopping recording process")

        self._process.terminate()

        try:
            self._process.wait(timeout=5)

        except subprocess.TimeoutExpired:

            logger.warning(
                "Recording reagiert nicht, Prozess wird beendet."
            )

            self._process.kill()
            self._process.wait()

        self._process = None
