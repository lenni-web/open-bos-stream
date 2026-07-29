"""Steuerung des separat laufenden Display-Dienstes."""

from __future__ import annotations

import shutil

from open_bos_stream.core.process import ProcessRunner
from open_bos_stream.display.config import DisplayConfig


class DisplayManager:
    SERVICE = "open-bos-display.service"

    def __init__(
        self,
        config: DisplayConfig,
        runner: ProcessRunner | None = None,
    ) -> None:
        self.config = config
        self._runner = runner or ProcessRunner()

    def reload(self, config: DisplayConfig) -> None:
        self.config = config

    @property
    def running(self) -> bool:
        if shutil.which("systemctl") is None:
            return False

        result = self._runner.run(
            [
                "systemctl",
                "is-active",
                "--quiet",
                self.SERVICE,
            ],
            timeout=3,
        )
        return result.returncode == 0

    def start(self) -> bool:
        if shutil.which("systemctl") is None:
            raise RuntimeError(
                "systemd ist auf diesem System nicht verfügbar."
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
        return self.running

    def stop(self) -> bool:
        if shutil.which("systemctl") is None:
            raise RuntimeError(
                "systemd ist auf diesem System nicht verfügbar."
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
        if shutil.which("systemctl") is None:
            raise RuntimeError(
                "systemd ist auf diesem System nicht verfügbar."
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
        return self.running

    def last_error(self) -> str | None:
        if shutil.which("journalctl") is None:
            return None

        result = self._runner.run(
            [
                "journalctl",
                "-u",
                self.SERVICE,
                "-n",
                "30",
                "--no-pager",
                "-o",
                "cat",
            ],
            timeout=3,
        )

        for line in reversed(result.stdout.splitlines()):
            if line.startswith("Display error:"):
                return line.removeprefix("Display error:").strip()

        return None

    def status(self) -> dict:
        running = self.running
        return {
            "enabled": self.config.enabled,
            "running": running,
            "mode": self.config.mode,
            "browser": self.config.browser,
            "error": (
                None
                if running or not self.config.enabled
                else self.last_error()
            ),
        }
