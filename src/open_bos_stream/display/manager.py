"""Steuerung des separat laufenden Display-Dienstes."""

from __future__ import annotations

import subprocess
import shutil

from open_bos_stream.display.config import DisplayConfig


class DisplayManager:
    SERVICE = "open-bos-display.service"

    def __init__(self, config: DisplayConfig) -> None:
        self.config = config

    def reload(self, config: DisplayConfig) -> None:
        self.config = config

    @property
    def running(self) -> bool:
        if shutil.which("systemctl") is None:
            return False

        result = subprocess.run(
            [
                "systemctl",
                "is-active",
                "--quiet",
                self.SERVICE,
            ],
            check=False,
        )
        return result.returncode == 0

    def start(self) -> bool:
        if shutil.which("systemctl") is None:
            raise RuntimeError(
                "systemd ist auf diesem System nicht verfügbar."
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
        return self.running

    def stop(self) -> bool:
        if shutil.which("systemctl") is None:
            raise RuntimeError(
                "systemd ist auf diesem System nicht verfügbar."
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
        if shutil.which("systemctl") is None:
            raise RuntimeError(
                "systemd ist auf diesem System nicht verfügbar."
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

    def last_error(self) -> str | None:
        if shutil.which("journalctl") is None:
            return None

        result = subprocess.run(
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
            capture_output=True,
            text=True,
            check=False,
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
