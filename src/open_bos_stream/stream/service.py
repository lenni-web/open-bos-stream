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

        try:
            result = subprocess.run(
                [
                    "journalctl",
                    "-u",
                    self.SERVICE,
                    "-n",
                    "40",
                    "--no-pager",
                    "-o",
                    "cat",
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

        for line in reversed(
            result.stdout.splitlines()
        ):

            for marker in (
                "Configuration error:",
                "Error opening input file ",
                "Error opening input:",
                "Input/output error",
                "too many reordered frames",
                "non monotonically increasing",
                "Permission denied",
                "Device or resource busy",
                "No such file or directory",
            ):
                if marker in line:
                    return line.strip()

        return None

    def diagnostics(self) -> dict:
        """Kompakte Laufzeitdiagnose für Dashboard und Support."""

        service = {
            "active_state": "external",
            "sub_state": "publisher",
            "restart_count": 0,
            "exit_status": None,
        }

        if self.managed:
            try:
                result = subprocess.run(
                    [
                        "systemctl",
                        "show",
                        self.SERVICE,
                        "--property=ActiveState,SubState,NRestarts,"
                        "ExecMainStatus",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=False,
                )
                values = {}
                for line in result.stdout.splitlines():
                    key, _, value = line.partition("=")
                    values[key] = value

                service = {
                    "active_state": values.get(
                        "ActiveState", "unknown"
                    ),
                    "sub_state": values.get("SubState", "unknown"),
                    "restart_count": int(
                        values.get("NRestarts", "0") or 0
                    ),
                    "exit_status": (
                        int(values["ExecMainStatus"])
                        if values.get("ExecMainStatus", "").isdigit()
                        else None
                    ),
                }
            except (OSError, subprocess.TimeoutExpired, ValueError):
                service["active_state"] = "unknown"
                service["sub_state"] = "unknown"

        return {
            "mode": (
                "managed_ffmpeg"
                if self.managed
                else "mediamtx_passthrough"
            ),
            "input_type": self._config.input.type,
            "input": (
                self._config.input.url
                if self._config.input.type == "rtmp"
                else self._config.input.device
            ),
            "configured_format": self._config.input.format,
            "configured_width": self._config.input.width,
            "configured_height": self._config.input.height,
            "configured_fps": self._config.input.fps,
            "encoder": self._config.encoder.codec,
            "output": self._config.stream.rtsp_url,
            "last_error": self.last_error(),
            **service,
        }

    def wait_until_ready(
        self,
        timeout: float = 8.0,
    ) -> bool:
        """Wartet, bis MediaMTX den konfigurierten Pfad empfängt."""

        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if (
                self.running
                and self._mediamtx.status(
                    self._config.stream.name
                ).ready
            ):
                return True

            time.sleep(0.25)

        return False

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

        time.sleep(1)

        return self.running

    def status(self) -> StreamStatus:

        return StreamStatus(
            running=self.running,
            pid=self.pid,
        )
