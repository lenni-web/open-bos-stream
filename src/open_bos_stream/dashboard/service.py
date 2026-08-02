"""
Dashboard Service

Stellt alle Informationen für das Web-Dashboard zentral bereit.
"""

from __future__ import annotations

import threading

from open_bos_stream.core.models import AppConfig
from open_bos_stream.core.installation import (
    installation_profile,
    server_access_settings,
)
from open_bos_stream.mediamtx.service import MediaMTXService
from open_bos_stream.media.storage import MediaStorageService
from open_bos_stream.recording.service import RecordingService
from open_bos_stream.stream.service import StreamService
from open_bos_stream.stream.probe import StreamProbeService
from open_bos_stream.stream.runtime_status import StreamRuntimeStatusStore
from open_bos_stream.stream.source_health import source_health
import time
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
        media_storage_service: MediaStorageService,
        stream_probe_service: StreamProbeService,
        runtime_status_store: StreamRuntimeStatusStore | None = None,
    ) -> None:

        self._config = config
        self._stream = stream_service
        self._health = health_service
        self._mediamtx = mediamtx_service
        self._recording = recording_service
        self._stream_output = stream_output_service
        self._system_info = system_info_service
        self._media_storage = media_storage_service
        self._probe = stream_probe_service
        self._runtime_status = (
            runtime_status_store or StreamRuntimeStatusStore()
        )
        self._stream_state: str | None = None
        self._state_since = time.monotonic()
        self._stable_since: float | None = None
        self._restart_baseline = 0
        self._status_lock = threading.RLock()
        self._cached_status: dict | None = None
        self._cached_status_at = 0.0

    def status(self) -> dict:
        """Bündelt gleichzeitige Browser-Polls in einem kurzen Cache."""

        with self._status_lock:
            now = time.monotonic()
            if (
                self._cached_status is not None
                and now - self._cached_status_at < 0.75
            ):
                return self._cached_status
            result = self._build_status()
            self._cached_status = result
            self._cached_status_at = time.monotonic()
            return result

    def _stability(
        self,
        state: str,
        restart_count: int,
    ) -> dict:
        now = time.monotonic()
        if state != self._stream_state:
            self._stream_state = state
            self._state_since = now

        if state in {"online", "repairing"}:
            if self._stable_since is None:
                self._stable_since = now
            stable_for = now - self._stable_since
            if stable_for >= 120:
                self._restart_baseline = restart_count
        else:
            self._stable_since = None
            stable_for = 0.0

        return {
            "state_for_seconds": int(now - self._state_since),
            "stable_for_seconds": int(stable_for),
            "restart_count_total": restart_count,
            "restart_count": max(
                0,
                restart_count - self._restart_baseline,
            ),
        }

    def _build_status(self) -> dict:
        """Aktuellen Dashboard-Status zurückgeben."""

        health = self._health.health()

        system_info = self._system_info.info()
        system_info_data = system_info.model_dump()
        system_info_data["installation_profile"] = installation_profile()
        system_info_data["server_access"] = server_access_settings()
        public_host = (
            server_access_settings()["public_domain"]
            or system_info.network.ipv4
        )

        enabled_sources = [
            item
            for item in self._config.sources
            if item.enabled
        ]
        requested_paths = list(dict.fromkeys([
            *(
                item.publish_path
                for item in enabled_sources
                if item.type == "rtmp"
            ),
            *(item.viewer_path for item in enabled_sources),
        ]))
        mediamtx_statuses = self._mediamtx.statuses(
            requested_paths
        )
        runtime_statuses = self._runtime_status.read()
        primary = enabled_sources[0] if enabled_sources else None
        mediamtx = (
            mediamtx_statuses[primary.viewer_path]
            if primary
            else self._mediamtx.status(self._config.stream.name)
        )

        recording = self._recording.status
        selected_media_source = next(
            (
                item
                for item in enabled_sources
                if item.id == self._config.media_capture.source_id
            ),
            enabled_sources[0] if enabled_sources else None,
        )

        stream_running = self._stream.running
        diagnostics = self._stream.diagnostics()
        probe = self._probe.cached_source_status(
            primary.id if primary else None,
            mediamtx.ready,
        )
        timestamp_warning = any(
            warning.get("code") in {
                "non_monotonic_dts",
                "missing_dts",
                "implausible_frame_rate",
                "irregular_packet_timing",
            }
            for warning in probe.get("warnings", [])
        )

        if not self._stream.managed and not mediamtx.ready:
            stream_state = "waiting_for_source"
            stream_message = (
                "Warte auf RTMP-Publisher an "
                f"'{self._config.stream.name}'."
            )
            stream_error = None
        elif (
            stream_running
            and mediamtx.ready
            and timestamp_warning
            and self._config.input.mode in {
                "copy_repair",
                "copy_repair_low_latency",
            }
        ):
            stream_state = "repairing"
            stream_message = (
                "Stream online; Zeitstempel-Reparatur für die "
                "instabile RTMP-Quelle ist aktiv."
            )
            stream_error = None
        elif stream_running and mediamtx.ready and timestamp_warning:
            stream_state = "unstable"
            stream_message = "Stream online, Eingangssignal ist instabil."
            stream_error = None
        elif stream_running and mediamtx.ready:
            stream_state = "online"
            stream_message = "Stream online."
            stream_error = None
        elif stream_running:
            stream_state = "connecting"
            stream_message = "Streamer gestartet; MediaMTX wartet."
            stream_error = None
        else:
            stream_error = self._stream.last_error()
            stream_state = "error" if stream_error else "stopped"
            stream_message = stream_error or "Stream gestoppt."

        stability = self._stability(
            stream_state,
            diagnostics.get("restart_count", 0),
        )
        diagnostics.update(stability)
        diagnostics["probe"] = probe

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

            "system_info": system_info_data,

            "media_storage": self._media_storage.status(),

            # -------------------------------------------------
            # Stream
            # -------------------------------------------------

            "stream": {

                "running": stream_running,

                "pid": self._stream.pid,

                "name": self._config.stream.name,

                "passthrough": not self._stream.managed,

                "controllable": self._stream.managed,

                "online": mediamtx.publisher,

                "protocol": (
                    (
                        self._config.input.type
                        if not self._stream.managed
                        else "rtsp"
                    )
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

                "state": stream_state,

                "message": stream_message,

                "error": stream_error,

                "diagnostics": diagnostics,

            },

            "sources": [
                {
                    "id": item.id,
                    "name": item.name,
                    "drone_type": item.drone_type,
                    "type": item.type,
                    "profile": item.profile,
                    "preview_active": bool(item.preview_url) or (
                        item.profile == "preview_transcode"
                    ),
                    "path": item.publish_path,
                    "viewer_path": item.viewer_path,
                    "fullscreen_viewer_path": (
                        item.fullscreen_viewer_path
                    ),
                    "publish_url": (
                        (
                            "rtmp://"
                            f"{public_host}:1935/"
                            f"{item.publish_path}"
                        )
                        if item.type == "rtmp"
                        else (
                            "Lokale Capture Card"
                            if item.type == "v4l2"
                            else f"{item.type.upper()}-Netzwerkquelle"
                        )
                    ),
                    "online": (
                        mediamtx_statuses[item.publish_path].publisher
                        if item.type == "rtmp"
                        else mediamtx_statuses[item.viewer_path].publisher
                    ),
                    "ready": mediamtx_statuses[item.viewer_path].ready,
                    "viewers": mediamtx_statuses[item.viewer_path].readers,
                    "codec": mediamtx_statuses[item.viewer_path].codec,
                    "width": mediamtx_statuses[item.viewer_path].width,
                    "height": mediamtx_statuses[item.viewer_path].height,
                    "tracks": mediamtx_statuses[item.viewer_path].tracks,
                    "runtime": runtime_statuses.get(item.id),
                    "managed": item.requires_process,
                    "health": source_health(
                        ready=mediamtx_statuses[item.viewer_path].ready,
                        online=(
                            mediamtx_statuses[item.publish_path].publisher
                            if item.type == "rtmp"
                            else mediamtx_statuses[item.viewer_path].publisher
                        ),
                        managed=item.requires_process,
                        runtime=runtime_statuses.get(item.id),
                    ),
                }
                for item in enabled_sources
            ],

            # -------------------------------------------------
            # Aufnahme
            # -------------------------------------------------

            "recording": {

                "active": recording.recording,

                "duration": recording.duration,

                "filename": recording.filename,

                "pid": recording.pid,

                "source_id": recording.source_id,

                "source_name": recording.source_name,

            },

            "media_capture": {
                "source_id": (
                    selected_media_source.id
                    if selected_media_source
                    else None
                ),
                "source_name": (
                    selected_media_source.name
                    if selected_media_source
                    else None
                ),
                "ready": (
                    mediamtx_statuses[
                        selected_media_source.viewer_path
                    ].ready
                    if selected_media_source
                    else False
                ),
            },

            # -------------------------------------------------

            # Streaming Outputs

            # -------------------------------------------------

            "stream_outputs": [
                output.model_dump()
                for output in self._stream_output.status
            ],

        }

    def probe_source(self, source_id: str) -> dict:
        source = next(
            (
                item
                for item in self._config.sources
                if item.enabled and item.id == source_id
            ),
            None,
        )
        if source is None:
            raise KeyError(source_id)
        if not self._mediamtx.status(source.viewer_path).ready:
            raise RuntimeError(
                "Die Quelle liefert momentan kein ausgabefähiges Signal."
            )
        return self._probe.probe_source(source)
