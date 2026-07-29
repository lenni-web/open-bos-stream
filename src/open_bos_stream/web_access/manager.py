"""Steuerung des systemd-Socket-Proxys für Port 80."""

from __future__ import annotations

import shutil
import socket

from open_bos_stream.core.process import ProcessRunner
from open_bos_stream.web_access.config import WebAccessConfig


class WebAccessManager:
    SOCKET = "open-bos-web-proxy.socket"
    SERVICE = "open-bos-web-proxy.service"
    STANDARD_PORT = 80
    FALLBACK_PORT = 8000

    def __init__(
        self,
        config: WebAccessConfig,
        runner: ProcessRunner | None = None,
    ) -> None:
        self.config = config
        self._runner = runner or ProcessRunner()

    def reload(self, config: WebAccessConfig) -> None:
        self.config = config

    @property
    def running(self) -> bool:
        if shutil.which("systemctl") is None:
            return False
        result = self._runner.run(
            ["systemctl", "is-active", "--quiet", self.SOCKET],
            timeout=3,
        )
        return result.returncode == 0

    @staticmethod
    def _port_occupied() -> bool:
        try:
            with socket.create_connection(
                ("127.0.0.1", WebAccessManager.STANDARD_PORT),
                timeout=0.25,
            ):
                return True
        except OSError:
            return False

    def start(self) -> bool:
        if shutil.which("systemctl") is None:
            raise RuntimeError("systemd ist auf diesem System nicht verfügbar.")
        if self.running:
            return True
        if self._port_occupied():
            raise RuntimeError(
                "Port 80 wird bereits von einem anderen Dienst verwendet. "
                "Die Oberfläche bleibt über Port 8000 erreichbar."
            )
        self._runner.run(
            ["sudo", "systemctl", "enable", "--now", self.SOCKET],
            timeout=10,
            check=True,
        )
        return self.running

    def stop(self) -> bool:
        if shutil.which("systemctl") is None:
            raise RuntimeError("systemd ist auf diesem System nicht verfügbar.")
        self._runner.run(
            ["sudo", "systemctl", "disable", "--now", self.SOCKET],
            timeout=10,
            check=True,
        )
        self._runner.run(
            ["sudo", "systemctl", "stop", self.SERVICE],
            timeout=10,
            check=True,
        )
        return not self.running

    def status(self) -> dict:
        running = self.running
        occupied = self._port_occupied()
        conflict = self.config.enabled and not running and occupied
        error = None
        if conflict:
            error = (
                "Port 80 wird bereits von einem anderen Dienst verwendet. "
                "Port 8000 ist weiterhin verfügbar."
            )
        elif self.config.enabled and not running:
            error = "Der Standard-Webzugriff ist konfiguriert, aber nicht aktiv."

        return {
            "enabled": self.config.enabled,
            "running": running,
            "standard_port": self.STANDARD_PORT,
            "fallback_port": self.FALLBACK_PORT,
            "port_available": running or not occupied,
            "conflict": conflict,
            "error": error,
        }
