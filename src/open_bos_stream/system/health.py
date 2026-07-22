"""
System Health Service
"""

from __future__ import annotations

import shutil

import psutil

from open_bos_stream.core.models import (
    AppConfig,
    ComponentStatus,
    HealthStatus,
    StreamStatus,
    SystemStatus,
)
from open_bos_stream.mediamtx.service import MediaMTXService
from open_bos_stream.stream.service import StreamService
from open_bos_stream.stream.source_manager import (
    SourceManager,
)


class HealthService:
    """Liefert den aktuellen Systemzustand."""

    def __init__(
        self,
        config: AppConfig,
        stream_service: StreamService,
        mediamtx_service: MediaMTXService,
    ) -> None:

        self._config = config
        self._stream = stream_service
        self._mediamtx = mediamtx_service

    @property
    def ffmpeg_available(self) -> bool:
        """Prüft, ob FFmpeg installiert ist."""

        return shutil.which("ffmpeg") is not None

    @property
    def input_available(self) -> bool:
        """Prüft, ob die aktive Eingangsquelle verfügbar ist."""

        from pathlib import Path

        manager = SourceManager.from_config(
            self._config,
        )

        source = manager.primary_source()

        if source is None:
            return False

        match source.type:

            case "v4l2":

                return Path(
                    source.device
                ).exists()

            case "rtsp" | "rtmp":

                return True

            case _:

                return False

    @property
    def cpu_usage(self) -> float:
        """CPU-Auslastung in Prozent."""

        return round(
            psutil.cpu_percent(interval=0.2),
            1,
        )

    @property
    def ram_usage(self) -> float:
        """RAM-Auslastung in Prozent."""

        return round(
            psutil.virtual_memory().percent,
            1,
        )

    @property
    def temperature(self) -> float:
        """CPU-Temperatur."""

        try:
            temperatures = psutil.sensors_temperatures()

            cpu = temperatures.get("cpu_thermal")

            if cpu:
                return round(cpu[0].current, 1)

        except Exception:
            pass

        return 0.0

    def health(self) -> HealthStatus:
        """Gesamten Systemstatus erzeugen."""

        stream = self._stream.status()
        mediamtx = self._mediamtx.status(
            self._config.stream.name,
        )

        return HealthStatus(
            capture=ComponentStatus(
                name="Input",
                online=self.input_available,
            ),
            ffmpeg=ComponentStatus(
                name="FFmpeg",
                online=self.ffmpeg_available,
            ),
            mediamtx=mediamtx,
            stream=StreamStatus(
                running=stream.running,
                pid=stream.pid,
            ),
            system=SystemStatus(
                cpu=self.cpu_usage,
                ram=self.ram_usage,
                temperature=self.temperature,
            ),
        )
