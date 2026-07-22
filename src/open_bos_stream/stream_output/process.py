"""
Streaming Output Process
"""

from __future__ import annotations

import logging
import subprocess
import time

logger = logging.getLogger(__name__)


class StreamOutputProcess:
    """Verwaltet einen FFmpeg-Restream-Prozess."""

    def __init__(self) -> None:

        self._process: subprocess.Popen | None = None

    @property
    def running(self) -> bool:

        return (
            self._process is not None
            and self._process.poll() is None
        )

    @property
    def pid(self) -> int | None:

        if self._process is None:
            return None

        return self._process.pid

    def start(
        self,
        command: list[str],
    ) -> None:

        if self.running:
            return

        logger.info(
            "Starting streaming output"
        )

        self._process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        time.sleep(0.5)

        if self._process.poll() is not None:

            error = self._process.stderr.read().strip()

            raise RuntimeError(error)

    def stop(self) -> None:

        if not self.running:
            return

        self._process.terminate()

        try:

            self._process.wait(
                timeout=5
            )

        except subprocess.TimeoutExpired:

            self._process.kill()

            self._process.wait()

        self._process = None
