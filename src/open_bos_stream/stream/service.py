"""
Streaming Service

Steuert den Stream über den systemd-Service
'open-bos-streamer.service'.
"""

from __future__ import annotations

import subprocess
import time

from open_bos_stream.core.models import AppConfig, StreamStatus
from open_bos_stream.mediamtx.service import MediaMTXService

class StreamService:

    SERVICE = "open-bos-streamer.service"

    def __init__(
        self,
        config: AppConfig,
        mediamtx_service: MediaMTXService,
    ) -> None:
        self._config = config
        self._mediamtx = mediamtx_service

    def reload(self, config: AppConfig) -> None:
        """Übernimmt eine bereits persistierte Konfiguration."""

        self._config = config

    @property
    def managed(self) -> bool:
        """True, wenn der interne FFmpeg-Dienst benötigt wird."""

        return not self._config.passthrough_active

    @property
    def running(self) -> bool:

        if not self.managed:
            return self._mediamtx.status(
                self._config.stream.name
            ).ready

        result = subprocess.run(
            [
                "systemctl",
                "is-active",
                "--quiet",
                self.SERVICE,
            ]
        )

        return result.returncode == 0

    @property
    def pid(self) -> int | None:

        if not self.managed:
            return None

        result = subprocess.run(
            [
                "systemctl",
                "show",
                self.SERVICE,
                "--property=MainPID",
                "--value",
            ],
            capture_output=True,
            text=True,
        )

        pid = result.stdout.strip()

        if pid in ("", "0"):
            return None

        return int(pid)

    def start(self) -> bool:

        if not self.managed:
            if self.running:
                return True

            raise RuntimeError(
                "Passthrough ist aktiv. Warte auf einen "
                f"Publisher am MediaMTX-Pfad "
                f"'{self._config.stream.name}'."
            )

        subprocess.run(
            [
                "sudo",
                "systemctl",
                "start",
                self.SERVICE,
            ],
            check=True,
        )

        time.sleep(1)

        if not self.running:

            error = self.last_error()

            raise RuntimeError(
                error or
                "Unable to start stream service."
            )

        return True

    def last_error(self) -> str | None:

        if not self.managed:
            return None

        result = subprocess.run(
            [
                "journalctl",
                "-u",
                self.SERVICE,
                "-n",
                "20",
                "--no-pager",
            ],
            capture_output=True,
            text=True,
        )

        for line in reversed(
            result.stdout.splitlines()
        ):

            if "Configuration error:" in line:

                return line.split(
                    "Configuration error:",
                    1,
                )[1].strip()

        return None

    def start_with_error(
        self,
    ) -> tuple[bool, str | None]:

        self.start()

        if self.running:
            return True, None

        return False, self.last_error()

    def stop(self) -> bool:

        if not self.managed:
            raise RuntimeError(
                "Ein Passthrough-Stream wird vom externen "
                "Publisher gesteuert und kann hier nicht "
                "gestoppt werden."
            )

        subprocess.run(
            [
                "sudo",
                "systemctl",
                "stop",
                self.SERVICE,
            ],
            check=True,
        )

        return not self.running

    def restart(self) -> bool:

        if not self.managed:
            raise RuntimeError(
                "Ein Passthrough-Stream wird vom externen "
                "Publisher gesteuert und kann hier nicht "
                "neu gestartet werden."
            )

        subprocess.run(
            [
                "sudo",
                "systemctl",
                "restart",
                self.SERVICE,
            ],
            check=True,
        )

        return self.running

    def status(self) -> StreamStatus:

        return StreamStatus(
            running=self.running,
            pid=self.pid,
        )
