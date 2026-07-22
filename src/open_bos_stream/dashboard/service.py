"""
Dashboard Service

Stellt alle Informationen für das Web-Dashboard zentral bereit.
"""

from __future__ import annotations

from open_bos_stream.core.models import AppConfig
from open_bos_stream.mediamtx.service import MediaMTXService
from open_bos_stream.recording.service import RecordingService
from open_bos_stream.stream.service import StreamService
from open_bos_stream.system.health import HealthService
from open_bos_stream.system.info import SystemInfoService
from open_bos_stream.stream_output.service import (
    StreamOutputService,
)

class DashboardService:
    """Aggregiert alle Dashboard-Daten."""

    def __init__(
        self,
        config: AppConfig,
        stream_service: StreamService,
        health_service: HealthService,
        mediamtx_service: MediaMTXService,
        recording_service: RecordingService,
        stream_output_service: StreamOutputService,
        system_info_service: SystemInfoService,
    ) -> None:

        self._config = config
        self._stream = stream_service
        self._health = health_service
        self._mediamtx = mediamtx_service
        self._recording = recording_service
        self._stream_output = stream_output_service
        self._system_info = system_info_service

    def status(self) -> dict:
        """Aktuellen Dashboard-Status zurückgeben."""

        health = self._health.health()

        system_info = self._system_info.info()

        mediamtx = self._mediamtx.status(
            self._config.stream.name
        )

        recording = self._recording.status

        return {

            # -------------------------------------------------
            # Dienste
            # -------------------------------------------------

            "services": {

                "capture": {
                    "name": health.capture.name,
                    "online": health.capture.online,
                },

                "ffmpeg": {
                    "name": health.ffmpeg.name,
                    "online": health.ffmpeg.online,
                },

                "mediamtx": {
                    "online": health.mediamtx.online,
                    "publisher": health.mediamtx.publisher,
                },

            },

            # -------------------------------------------------
            # System
            # -------------------------------------------------

            "system": {

                "cpu": health.system.cpu,
                "ram": health.system.ram,
                "temperature": health.system.temperature,

            },

            "system_info": system_info.model_dump(),

            # -------------------------------------------------
            # Stream
            # -------------------------------------------------

            "stream": {

                "running": self._stream.running,

                "pid": self._stream.pid,

                "name": self._config.stream.name,

                "online": mediamtx.publisher,

                "protocol": (
                    "rtsp"
                    if mediamtx.publisher
                    else "offline"
                ),

                "viewers": mediamtx.readers,

                "ready": mediamtx.ready,

                "source": mediamtx.source,

                "tracks": mediamtx.tracks,

                "codec": mediamtx.codec,

                "width": mediamtx.width,

                "height": mediamtx.height,

                "bytes_received": mediamtx.bytes_received,

                "bytes_sent": mediamtx.bytes_sent,

                "online_time": mediamtx.online_time,

            },

            # -------------------------------------------------
            # Aufnahme
            # -------------------------------------------------

            "recording": {

                "active": recording.recording,

                "duration": recording.duration,

                "filename": recording.filename,

                "pid": recording.pid,

            },

            # -------------------------------------------------

            # Streaming Outputs

            # -------------------------------------------------

            "stream_outputs": [
                output.model_dump()
                for output in self._stream_output.status
            ],

        }
