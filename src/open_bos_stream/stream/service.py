"""
Streaming Service

Steuert den Stream über den systemd-Service
'open-bos-streamer.service'.
"""

from __future__ import annotations

import time

from open_bos_stream.core.models import AppConfig, StreamStatus
from open_bos_stream.core.process import ProcessRunner
from open_bos_stream.mediamtx.service import MediaMTXService

class StreamService:

    SERVICE = "open-bos-streamer.service"

    def __init__(
        self,
        config: AppConfig,
        mediamtx_service: MediaMTXService,
        runner: ProcessRunner | None = None,
    ) -> None:
        self._config = config
        self._mediamtx = mediamtx_service
        self._runner = runner or ProcessRunner()

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

        result = self._runner.run(
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

        result = self._runner.run(
            [
                "systemctl",
                "show",
                self.SERVICE,
                "--property=MainPID",
                "--value",
            ],
            timeout=3,
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

        self._runner.run(
            [
                "sudo",
                "systemctl",
                "start",
                self.SERVICE,
            ],
            timeout=10,
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

    @staticmethod
    def _classify_error(line: str) -> tuple[str, str]:
        categories = (
            (
                ("Permission denied",),
                "permission",
                "Berechtigungen für Gerät oder Datei prüfen.",
            ),
            (
                ("Device or resource busy",),
                "device_busy",
                "Prüfen, ob ein anderer Prozess die Quelle verwendet.",
            ),
            (
                ("No such file or directory",),
                "missing_resource",
                "Gerätepfad oder Datei in der Konfiguration prüfen.",
            ),
            (
                (
                    "too many reordered frames",
                    "non monotonically increasing",
                ),
                "timestamps",
                "Zeitstempel der Eingangsquelle sind instabil.",
            ),
            (
                (
                    "Error opening input",
                    "Input/output error",
                ),
                "input_unavailable",
                "Eingangsquelle und Verbindung prüfen.",
            ),
            (
                ("Unknown encoder", "Encoder not found"),
                "encoder",
                "Konfigurierten Encoder und FFmpeg prüfen.",
            ),
            (
                ("Configuration error:",),
                "configuration",
                "Stream-Konfiguration prüfen.",
            ),
        )
        for markers, category, advice in categories:
            if any(marker in line for marker in markers):
                return category, advice
        return "unknown", "Dienstprotokoll für Details prüfen."

    def last_error_details(self) -> dict | None:

        if not self.managed:
            return None

        try:
            properties = self._runner.run(
                [
                    "systemctl",
                    "show",
                    self.SERVICE,
                    "--property=ExecMainStartTimestamp",
                    "--value",
                ],
                timeout=3,
            )
            command = [
                "journalctl",
                "-b",
                "-u",
                self.SERVICE,
                "-n",
                "80",
                "--no-pager",
                "-o",
                "short-iso",
            ]
            started = properties.stdout.strip()
            if started:
                command.extend(["--since", started])
            result = self._runner.run(command, timeout=3)
        except (RuntimeError, TimeoutError):
            return None

        markers = (
            "Configuration error:",
            "Error opening input file ",
            "Error opening input:",
            "Input/output error",
            "too many reordered frames",
            "non monotonically increasing",
            "Permission denied",
            "Device or resource busy",
            "No such file or directory",
            "Unknown encoder",
            "Encoder not found",
        )
        for line in reversed(result.stdout.splitlines()):
            if any(marker in line for marker in markers):
                clean = line.strip()
                timestamp = clean.split(" ", 1)[0]
                category, advice = self._classify_error(clean)
                return {
                    "timestamp": timestamp,
                    "category": category,
                    "message": clean,
                    "advice": advice,
                }

        return None

    def last_error(self) -> str | None:
        details = self.last_error_details()
        return details["message"] if details else None

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
                result = self._runner.run(
                    [
                        "systemctl",
                        "show",
                        self.SERVICE,
                        "--property=ActiveState,SubState,NRestarts,"
                        "ExecMainStatus,ExecMainStartTimestamp",
                    ],
                    timeout=3,
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
                    "started_at": values.get(
                        "ExecMainStartTimestamp"
                    ) or None,
                }
            except (RuntimeError, TimeoutError, ValueError):
                service["active_state"] = "unknown"
                service["sub_state"] = "unknown"

        error_details = self.last_error_details()

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
            "last_error": (
                error_details["message"]
                if error_details
                else None
            ),
            "last_error_details": error_details,
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

        self._runner.run(
            [
                "sudo",
                "systemctl",
                "stop",
                self.SERVICE,
            ],
            timeout=10,
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

        self._runner.run(
            [
                "sudo",
                "systemctl",
                "restart",
                self.SERVICE,
            ],
            timeout=10,
            check=True,
        )

        time.sleep(1)

        return self.running

    def status(self) -> StreamStatus:

        return StreamStatus(
            running=self.running,
            pid=self.pid,
        )
