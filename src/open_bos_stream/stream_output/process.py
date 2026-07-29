"""
Streaming Output Process
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from collections import deque

logger = logging.getLogger(__name__)


class StreamOutputProcess:
    """Verwaltet einen FFmpeg-Restream-Prozess."""

    def __init__(self) -> None:

        self._process: subprocess.Popen | None = None
        self._stderr: deque[str] = deque(maxlen=80)
        self._reader: threading.Thread | None = None

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

        self._stderr.clear()

        try:
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise RuntimeError(
                f"FFmpeg konnte nicht gestartet werden: {exc}"
            ) from exc

        self._reader = threading.Thread(
            target=self._read_stderr,
            name="open-bos-stream-output-log",
            daemon=True,
        )
        self._reader.start()

        deadline = time.monotonic() + 1.5
        while (
            self._process.poll() is None
            and time.monotonic() < deadline
        ):
            time.sleep(0.1)

        if self._process.poll() is not None:
            if self._reader:
                self._reader.join(timeout=0.5)
            raise RuntimeError(
                self.last_error
                or (
                    "FFmpeg wurde unmittelbar nach dem Start "
                    f"beendet (Exit {self._process.returncode})."
                )
            )

    def _read_stderr(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return

        for line in process.stderr:
            clean = line.strip()
            if clean:
                self._stderr.append(clean)

    @property
    def last_error(self) -> str | None:
        if not self._stderr:
            return None

        relevant = list(self._stderr)[-8:]
        return "\n".join(relevant)

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
        self._reader = None
