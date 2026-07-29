"""Vorabprüfung einer Stream-Konfiguration."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

from open_bos_stream.core.models import AppConfig
from open_bos_stream.core.process import ProcessRunner
from open_bos_stream.stream.command import FFmpegCommandBuilder


class ConfigPreflightError(RuntimeError):
    """Die Konfiguration kann nicht sicher aktiviert werden."""


class ConfigPreflightValidator:
    """Prüft Laufzeitvoraussetzungen ohne Dienste zu verändern."""

    def __init__(self, runner: ProcessRunner | None = None) -> None:
        self._runner = runner or ProcessRunner()

    @staticmethod
    def _valid_url(value: str | None, schemes: set[str]) -> bool:
        if not value:
            return False

        parsed = urlparse(value)
        return parsed.scheme in schemes and bool(parsed.hostname)

    def _available_encoders(self) -> str:
        try:
            result = self._runner.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                timeout=5,
            )
        except (RuntimeError, TimeoutError) as exc:
            raise ConfigPreflightError(
                "FFmpeg konnte für die Encoder-Prüfung nicht "
                "ausgeführt werden."
            ) from exc

        if result.returncode != 0:
            raise ConfigPreflightError(
                "FFmpeg konnte die verfügbaren Encoder nicht ermitteln."
            )

        return result.stdout

    def validate(self, config: AppConfig) -> list[str]:
        checks: list[str] = []

        if config.passthrough_active:
            if not self._valid_url(config.input.url, {"rtmp", "rtmps"}):
                raise ConfigPreflightError(
                    "Die RTMP-Eingangs-URL ist ungültig."
                )

            if not config.stream.name.strip("/"):
                raise ConfigPreflightError(
                    "Der MediaMTX-Pfad darf nicht leer sein."
                )

            checks.extend([
                "RTMP-Eingangs-URL gültig",
                "MediaMTX-Pfad gültig",
                "Kein interner FFmpeg-Neustart erforderlich",
            ])
            return checks

        if config.input.type == "v4l2":
            device = Path(config.input.device or "")
            if not device.exists():
                raise ConfigPreflightError(
                    f"Capture-Gerät '{device}' ist nicht verfügbar."
                )
            if not os.access(device, os.R_OK | os.W_OK):
                raise ConfigPreflightError(
                    f"Keine ausreichenden Berechtigungen für '{device}'."
                )
            checks.append(f"Capture-Gerät zugreifbar ({device})")

        if config.source_profile == "rtmp_repair":
            if not self._valid_url(config.input.url, {"rtmp", "rtmps"}):
                raise ConfigPreflightError(
                    "Die RTMP-Eingangs-URL ist ungültig."
                )
            input_path = urlparse(config.input.url or "").path.strip("/")
            output_path = urlparse(config.stream.rtsp_url).path.strip("/")
            if input_path == output_path:
                raise ConfigPreflightError(
                    "RTMP-Eingang und reparierte Ausgabe dürfen nicht "
                    "denselben MediaMTX-Pfad verwenden."
                )
            checks.append("Getrennte RTMP-Eingangs- und Ausgabepfade")

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise ConfigPreflightError(
                "FFmpeg ist nicht installiert oder nicht im PATH."
            )
        checks.append(f"FFmpeg verfügbar ({ffmpeg})")

        if not self._valid_url(config.stream.rtsp_url, {"rtsp", "rtsps"}):
            raise ConfigPreflightError(
                "Die RTSP-Ausgabe-URL ist ungültig."
            )
        checks.append("RTSP-Ausgabe-URL gültig")

        try:
            command = FFmpegCommandBuilder(config).build()
        except Exception as exc:
            raise ConfigPreflightError(
                f"FFmpeg-Befehl konnte nicht erzeugt werden: {exc}"
            ) from exc

        if not command or command[0] != "ffmpeg":
            raise ConfigPreflightError(
                "Der erzeugte FFmpeg-Befehl ist ungültig."
            )
        checks.append("FFmpeg-Befehl erfolgreich erzeugt")

        codec = config.encoder.codec
        if codec != "copy":
            encoders = self._available_encoders()
            if codec not in encoders:
                raise ConfigPreflightError(
                    f"Der Encoder '{codec}' ist in FFmpeg nicht verfügbar."
                )
            checks.append(f"Encoder verfügbar ({codec})")

        return checks
