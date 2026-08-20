"""Eng begrenzte Systemfunktionen für Superadministratoren."""

from __future__ import annotations

import re

from open_bos_stream.core.process import ProcessRunner


SYSTEM_HELPER_DIR = "/usr/local/libexec/open-bos-stream"
STREAM_LOG_HELPER = f"{SYSTEM_HELPER_DIR}/stream-log"
REBOOT_HELPER = f"{SYSTEM_HELPER_DIR}/reboot"


class SystemAdministrationService:
    """Ruft ausschließlich root-eigene Helfer ohne Benutzerparameter auf."""

    def __init__(self, runner: ProcessRunner | None = None) -> None:
        self._runner = runner or ProcessRunner()

    @staticmethod
    def redact_log(value: str) -> str:
        """Entfernt Zugangsdaten und bekannte Geheimnisparameter."""

        value = re.sub(
            r"(?i)([?&](?:token|password|pass|key)=)[^&\s\"']+",
            r"\1***",
            value,
        )
        value = re.sub(
            r"(?i)(\b(?:publish_token|password|token)\s*[:=]\s*)\S+",
            r"\1***",
            value,
        )
        return re.sub(
            r"(?i)([a-z][a-z0-9+.-]*://)([^/@\s:]+):([^/@\s]+)@",
            r"\1***:***@",
            value,
        )

    def stream_log(self) -> str:
        result = self._runner.run(
            ["sudo", STREAM_LOG_HELPER],
            timeout=8,
            check=True,
        )
        return self.redact_log(result.stdout)[-200_000:]

    def schedule_reboot(self) -> None:
        self._runner.run(
            ["sudo", REBOOT_HELPER],
            timeout=5,
            check=True,
        )
