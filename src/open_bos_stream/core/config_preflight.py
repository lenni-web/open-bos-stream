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

        enabled = [source for source in config.sources if source.enabled]
        if not enabled:
            checks.append("Keine Quelle aktiviert")
            return checks

        managed = [source for source in enabled if source.requires_process]

        # Konkrete Quellenfehler vor allgemeinen Abhängigkeiten melden.
        for source in enabled:
            if source.type == "v4l2":
                device = Path(source.device or "")
                if not device.exists():
                    raise ConfigPreflightError(
                        f"Capture-Gerät '{device}' der Quelle "
                        f"'{source.name}' ist nicht verfügbar."
                    )
            schemes = {
                "rtsp": {"rtsp", "rtsps"},
                "srt": {"srt"},
                "udp": {"udp"},
                "http": {"http", "https"},
                "hls": {"http", "https"},
            }.get(source.type)
            if schemes and not self._valid_url(source.url, schemes):
                raise ConfigPreflightError(
                    f"{source.type.upper()}-URL der Quelle "
                    f"'{source.name}' ist ungültig."
                )

        if managed:
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise ConfigPreflightError(
                    "FFmpeg ist nicht installiert oder nicht im PATH."
                )
            checks.append(f"FFmpeg verfügbar ({ffmpeg})")

        encoders: str | None = None
        builder = FFmpegCommandBuilder(config)

        for source in enabled:
            if source.type == "v4l2":
                device = Path(source.device or "")
                if not os.access(device, os.R_OK | os.W_OK):
                    raise ConfigPreflightError(
                        f"Keine ausreichenden Berechtigungen für '{device}'."
                    )

            if not source.requires_process:
                checks.append(
                    f"{source.name}: direkter RTMP-Pfad '{source.id}'"
                )
                continue

            try:
                command = builder.build_source(source)
            except Exception as exc:
                raise ConfigPreflightError(
                    f"FFmpeg-Befehl für '{source.name}' konnte nicht "
                    f"erzeugt werden: {exc}"
                ) from exc

            if not command or command[0] != "ffmpeg":
                raise ConfigPreflightError(
                    f"FFmpeg-Befehl für '{source.name}' ist ungültig."
                )

            codec = (
                "libx264"
                if source.is_preview_transcode
                else (
                    source.codec or config.encoder.codec
                    if source.profile == "transcode"
                    else "copy"
                )
            )
            if codec != "copy":
                encoders = encoders or self._available_encoders()
                if codec not in encoders:
                    raise ConfigPreflightError(
                        f"Encoder '{codec}' für '{source.name}' ist "
                        "in FFmpeg nicht verfügbar."
                    )
            checks.append(f"{source.name}: FFmpeg-Befehl gültig")

        return checks
