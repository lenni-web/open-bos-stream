"""Bedarfsgesteuerte Hauptstreams für die Vollbildanzeige."""

from __future__ import annotations

import logging
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field

from open_bos_stream.core.models import AppConfig, SourceConfig
from open_bos_stream.mediamtx.client import MediaMTXClient
from open_bos_stream.stream.command import FFmpegCommandBuilder

logger = logging.getLogger(__name__)

LEASE_SECONDS = 30.0
STOP_GRACE_SECONDS = 10.0


def _video_details(path: dict | None) -> tuple[int, int, str | None]:
    if not path:
        return 0, 0, None
    width = int(path.get("width") or 0)
    height = int(path.get("height") or 0)
    codec = path.get("codec")
    for track in path.get("tracks2") or []:
        props = track.get("codecProps") or {}
        if props.get("width") or props.get("height"):
            width = int(props.get("width") or width)
            height = int(props.get("height") or height)
            codec = track.get("codec") or codec
            break
    return width, height, codec


@dataclass
class FullscreenRelay:
    source: SourceConfig
    process: subprocess.Popen[bytes] | None
    leases: dict[str, float] = field(default_factory=dict)
    idle_since: float | None = None


class FullscreenRelayManager:
    """Teilt einen Hauptstream-Relay zwischen allen Vollbildnutzern."""

    def __init__(
        self,
        config: AppConfig,
        mediamtx: MediaMTXClient,
    ) -> None:
        self._config = config
        self._mediamtx = mediamtx
        self._builder = FFmpegCommandBuilder(config)
        self._relays: dict[str, FullscreenRelay] = {}
        self._lock = threading.RLock()
        self._stopping = threading.Event()
        self._monitor = threading.Thread(
            target=self._monitor_relays,
            name="fullscreen-relay-monitor",
            daemon=True,
        )
        self._monitor.start()

    def _source(self, source_id: str) -> SourceConfig:
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
        if source.fullscreen_viewer_path == source.viewer_path:
            raise ValueError(
                "Für diese Quelle ist kein separater Hauptstream konfiguriert."
            )
        return source

    def acquire(self, source_id: str) -> dict:
        source = self._source(source_id)
        now = time.monotonic()
        lease_id = uuid.uuid4().hex
        with self._lock:
            relay = self._relays.get(source_id)
            process_ended = (
                relay is not None
                and relay.process is not None
                and relay.process.poll() is not None
            )
            if relay is None or process_ended:
                process: subprocess.Popen[bytes] | None = None
                if not (
                    source.type == "rtmp"
                    and source.is_preview_transcode
                ):
                    command = self._builder.build_source(
                        source,
                        use_preview=False,
                        viewer_path=source.fullscreen_viewer_path,
                    )
                    process = subprocess.Popen(
                        [
                            command[0],
                            "-hide_banner",
                            "-loglevel",
                            "warning",
                            "-nostdin",
                            *command[1:],
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                relay = FullscreenRelay(source=source, process=process)
                self._relays[source_id] = relay
                logger.info(
                    "Hauptstream für Quelle %s bereitgestellt (PID %s)",
                    source_id,
                    process.pid if process is not None else "direkt",
                )
            relay.leases[lease_id] = now + LEASE_SECONDS
            relay.idle_since = None
        return self.status(source_id, lease_id)

    def status(self, source_id: str, lease_id: str) -> dict:
        now = time.monotonic()
        with self._lock:
            relay = self._relays.get(source_id)
            if relay is None or lease_id not in relay.leases:
                raise KeyError(lease_id)
            relay.leases[lease_id] = now + LEASE_SECONDS
            running = (
                relay.process is None
                or relay.process.poll() is None
            )
            viewer_path = relay.source.fullscreen_viewer_path
        path = self._mediamtx.path(viewer_path) if running else None
        width, height, codec = _video_details(path)
        return {
            "source_id": source_id,
            "viewer_path": viewer_path,
            "lease_id": lease_id,
            "running": running,
            "ready": bool(path and path.get("ready")),
            "width": width,
            "height": height,
            "codec": codec,
        }

    def release(self, source_id: str, lease_id: str) -> None:
        with self._lock:
            relay = self._relays.get(source_id)
            if relay is None:
                return
            relay.leases.pop(lease_id, None)
            if not relay.leases and relay.idle_since is None:
                relay.idle_since = time.monotonic()

    def _stop_relay(self, source_id: str, relay: FullscreenRelay) -> None:
        if relay.process is not None and relay.process.poll() is None:
            try:
                relay.process.send_signal(signal.SIGINT)
                relay.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                relay.process.kill()
            except ProcessLookupError:
                pass
        self._relays.pop(source_id, None)
        logger.info("Hauptstream für Quelle %s freigegeben", source_id)

    def _monitor_relays(self) -> None:
        while not self._stopping.wait(1.0):
            now = time.monotonic()
            with self._lock:
                for source_id, relay in list(self._relays.items()):
                    relay.leases = {
                        key: expires
                        for key, expires in relay.leases.items()
                        if expires > now
                    }
                    if (
                        relay.process is not None
                        and relay.process.poll() is not None
                    ):
                        self._stop_relay(source_id, relay)
                        continue
                    if relay.leases:
                        relay.idle_since = None
                        continue
                    relay.idle_since = relay.idle_since or now
                    if now - relay.idle_since >= STOP_GRACE_SECONDS:
                        self._stop_relay(source_id, relay)

    def close(self) -> None:
        self._stopping.set()
        self._monitor.join(timeout=2)
        with self._lock:
            for source_id, relay in list(self._relays.items()):
                self._stop_relay(source_id, relay)
