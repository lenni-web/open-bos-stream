"""Systemd-supervised multi-source FFmpeg runner."""

from __future__ import annotations

import signal
import subprocess
import sys
import threading
import time
import zlib
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

import psutil

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.models import SourceConfig
from open_bos_stream.mediamtx.client import MediaMTXClient
from open_bos_stream.stream.command import FFmpegCommandBuilder
from open_bos_stream.stream.exceptions import ConfigurationError
from open_bos_stream.stream.progress import FFmpegProgress
from open_bos_stream.stream.runtime_status import StreamRuntimeStatusStore


STARTUP_GRACE_SECONDS = 20.0
STALE_TIMEOUT_SECONDS = 12.0
STABLE_RESET_SECONDS = 30.0
FORCE_KILL_SECONDS = 5.0


@dataclass
class SourceProcess:
    process: subprocess.Popen[str]
    started_at: float
    progress: FFmpegProgress = field(default_factory=FFmpegProgress)
    stale_since: float | None = None
    cpu_percent: float = 0.0
    memory_bytes: int = 0
    resource_process: psutil.Process | None = None
    previous_drop_frames: int = 0
    previous_dup_frames: int = 0
    last_drop_at: float | None = None
    last_dup_at: float | None = None

    def sample_resources(self) -> None:
        try:
            if self.resource_process is None:
                self.resource_process = psutil.Process(self.process.pid)
                self.resource_process.cpu_percent(interval=None)
            else:
                self.cpu_percent = self.resource_process.cpu_percent(
                    interval=None
                )
            self.memory_bytes = self.resource_process.memory_info().rss
        except (psutil.Error, OSError):
            self.resource_process = None

    def sample_timing_events(self, *, wall_now: float) -> None:
        if self.progress.dropped_frames > self.previous_drop_frames:
            self.last_drop_at = wall_now
        if self.progress.duplicated_frames > self.previous_dup_frames:
            self.last_dup_at = wall_now
        self.previous_drop_frames = self.progress.dropped_frames
        self.previous_dup_frames = self.progress.duplicated_frames


@dataclass
class RestartState:
    count: int = 0
    last_reason: str | None = None
    last_at: float | None = None

    def record(self, reason: str) -> None:
        self.count += 1
        self.last_reason = reason
        self.last_at = time.time()


def _staggered_delay(source_id: str, base_delay: float) -> float:
    """Verteilt gleichzeitige Reconnects reproduzierbar um bis zu 20 %."""

    bucket = zlib.crc32(source_id.encode("utf-8")) % 21
    return min(36.0, base_delay * (1.0 + bucket / 100.0))


def _ready_paths(items: list[dict]) -> set[str]:
    """Extrahiert tatsächlich verfügbare Publisherpfade aus MediaMTX."""

    return {
        str(item.get("name"))
        for item in items
        if item.get("name") and item.get("ready")
    }


def _waiting_for_publisher(
    source: SourceConfig,
    ready_paths: set[str],
) -> bool:
    return (
        source.type == "rtmp"
        and source.publish_path not in ready_paths
    )


def _read_progress(runtime: SourceProcess) -> None:
    """Leert die FFmpeg-Pipe und aktualisiert den Medienfortschritt."""

    stdout = runtime.process.stdout
    if stdout is None:
        return
    for line in stdout:
        runtime.progress.feed(line)


def _signal_process(
    process: subprocess.Popen[str],
    signal_number: int,
) -> None:
    """Signalisiert ohne Race-Fehler, falls FFmpeg gerade selbst endet."""

    try:
        process.send_signal(signal_number)
    except ProcessLookupError:
        pass


def _runtime_snapshot(
    source_ids: list[str],
    processes: dict[str, SourceProcess],
    restart_at: dict[str, float],
    restart_states: dict[str, RestartState],
    waiting_for_source: set[str] | None = None,
    *,
    now: float,
) -> dict[str, dict]:
    snapshot: dict[str, dict] = {}
    waiting_for_source = waiting_for_source or set()
    wall_now = time.time()
    for source_id in source_ids:
        runtime = processes.get(source_id)
        restart = restart_states[source_id]
        if runtime is None:
            snapshot[source_id] = {
                "state": (
                    "waiting_source"
                    if source_id in waiting_for_source
                    else "waiting_restart"
                ),
                "restart_in": max(0.0, restart_at[source_id] - now),
                "restart_count": restart.count,
                "last_restart_reason": restart.last_reason,
                "last_restart_at": restart.last_at,
            }
            continue

        progress = runtime.progress
        snapshot[source_id] = {
            "state": (
                "restarting"
                if runtime.stale_since is not None
                else (
                    "running"
                    if progress.last_advance is not None
                    else "starting"
                )
            ),
            "frame": progress.frame,
            "fps": progress.fps,
            "speed": progress.speed,
            "drop_frames": progress.dropped_frames,
            "dup_frames": progress.duplicated_frames,
            "cpu_percent": runtime.cpu_percent,
            "memory_bytes": runtime.memory_bytes,
            "last_drop_at": runtime.last_drop_at,
            "last_dup_at": runtime.last_dup_at,
            "restart_count": restart.count,
            "last_restart_reason": (
                "stale"
                if runtime.stale_since is not None
                else restart.last_reason
            ),
            "last_restart_at": restart.last_at,
            "last_progress_at": (
                wall_now - max(0.0, now - progress.last_advance)
                if progress.last_advance is not None
                else None
            ),
        }
    return snapshot


def _redact(argument: str) -> str:
    if "://" not in argument:
        return argument
    try:
        parsed = urlsplit(argument)
    except ValueError:
        return argument
    if parsed.password is None and not parsed.query:
        return argument
    if parsed.password is None:
        netloc = parsed.netloc
    else:
        hostname = parsed.hostname or ""
        if ":" in hostname:
            hostname = f"[{hostname}]"
        netloc = f"{parsed.username or ''}:***@{hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
    return urlunsplit((
        parsed.scheme,
        netloc,
        parsed.path,
        "***" if parsed.query else "",
        parsed.fragment,
    ))


def main() -> int:
    config = ConfigLoader().load()
    sources = [
        source
        for source in config.sources
        if source.enabled and source.requires_process
    ]

    if not sources:
        print(
            "Keine verwalteten Quellen konfiguriert; "
            "direkte RTMP-Eingänge laufen über MediaMTX.",
            flush=True,
        )
        return 0

    builder = FFmpegCommandBuilder(config)
    sources_by_id = {source.id: source for source in sources}
    mediamtx = MediaMTXClient(timeout=0.75)
    commands: dict[str, list[str]] = {}
    processes: dict[str, SourceProcess] = {}
    restart_at: dict[str, float] = {}
    backoff: dict[str, float] = {}
    restart_states: dict[str, RestartState] = {}
    waiting_for_source: set[str] = set()
    available_rtmp_paths: set[str] = set()
    last_path_check = 0.0
    status_store = StreamRuntimeStatusStore()
    last_status_write = 0.0
    stopping = False

    def stop_children(*_: object) -> None:
        nonlocal stopping
        stopping = True
        for runtime in processes.values():
            if runtime.process.poll() is None:
                _signal_process(runtime.process, signal.SIGINT)

    signal.signal(signal.SIGINT, stop_children)
    signal.signal(signal.SIGTERM, stop_children)

    try:
        for source in sources:
            command = builder.build_source(source)
            commands[source.id] = command
            backoff[source.id] = 1.0
            restart_at[source.id] = 0.0
            restart_states[source.id] = RestartState()
            print("=" * 48, flush=True)
            print(
                f"Quelle {source.id}: {source.name} "
                f"({source.type}/{source.profile})",
                flush=True,
            )
            print(" ".join(_redact(item) for item in command), flush=True)

        while not stopping:
            now = time.monotonic()
            if now - last_path_check >= 0.75:
                available_rtmp_paths = _ready_paths(mediamtx.paths())
                last_path_check = now
            for source_id, command in commands.items():
                source = sources_by_id[source_id]
                runtime = processes.get(source_id)
                if runtime is None:
                    if _waiting_for_publisher(
                        source,
                        available_rtmp_paths,
                    ):
                        if source_id not in waiting_for_source:
                            print(
                                f"Quelle {source_id}: warte auf "
                                "RTMP-Publisher.",
                                flush=True,
                            )
                        waiting_for_source.add(source_id)
                        restart_at[source_id] = now
                        backoff[source_id] = 1.0
                        continue
                    if source_id in waiting_for_source:
                        print(
                            f"Quelle {source_id}: RTMP-Publisher erkannt; "
                            "Verarbeitung startet.",
                            flush=True,
                        )
                        waiting_for_source.discard(source_id)
                    if now < restart_at[source_id]:
                        continue
                    try:
                        monitored_command = [
                            command[0],
                            "-hide_banner",
                            "-loglevel",
                            "warning",
                            "-nostdin",
                            "-nostats",
                            "-progress",
                            "pipe:1",
                            "-stats_period",
                            "1",
                            *command[1:],
                        ]
                        process = subprocess.Popen(
                            monitored_command,
                            stdout=subprocess.PIPE,
                            text=True,
                            bufsize=1,
                        )
                        runtime = SourceProcess(
                            process=process,
                            started_at=now,
                        )
                        processes[source_id] = runtime
                        threading.Thread(
                            target=_read_progress,
                            args=(runtime,),
                            name=f"progress-{source_id}",
                            daemon=True,
                        ).start()
                    except OSError as exc:
                        delay = backoff[source_id]
                        actual_delay = _staggered_delay(source_id, delay)
                        restart_states[source_id].record("start_failed")
                        print(
                            f"Quelle {source_id} konnte nicht gestartet "
                            f"werden: {exc}; neuer Versuch in "
                            f"{actual_delay:.1f}s.",
                            file=sys.stderr,
                            flush=True,
                        )
                        restart_at[source_id] = now + actual_delay
                        backoff[source_id] = min(delay * 2, 30)
                    continue

                process = runtime.process
                returncode = process.poll()
                if returncode is not None:
                    if _waiting_for_publisher(
                        source,
                        available_rtmp_paths,
                    ):
                        processes.pop(source_id, None)
                        waiting_for_source.add(source_id)
                        restart_at[source_id] = now
                        backoff[source_id] = 1.0
                        print(
                            f"Quelle {source_id}: RTMP-Publisher nicht "
                            "mehr verfügbar; warte auf neues Signal.",
                            flush=True,
                        )
                        continue
                    delay = backoff[source_id]
                    actual_delay = _staggered_delay(source_id, delay)
                    reason = (
                        "stale"
                        if runtime.stale_since is not None
                        else f"exit_{returncode}"
                    )
                    restart_states[source_id].record(reason)
                    print(
                        f"Quelle {source_id} beendet "
                        f"(Exit {returncode}); neuer Versuch "
                        f"in {actual_delay:.1f}s.",
                        file=sys.stderr,
                        flush=True,
                    )
                    processes.pop(source_id, None)
                    restart_at[source_id] = now + actual_delay
                    backoff[source_id] = min(delay * 2, 30)
                    continue

                running_for = now - runtime.started_at
                if running_for >= STABLE_RESET_SECONDS:
                    backoff[source_id] = 1.0

                if runtime.stale_since is not None:
                    if now - runtime.stale_since >= FORCE_KILL_SECONDS:
                        print(
                            f"Quelle {source_id}: FFmpeg reagiert nicht; "
                            "Prozess wird beendet.",
                            file=sys.stderr,
                            flush=True,
                        )
                        _signal_process(process, signal.SIGKILL)
                    continue

                if runtime.progress.stale(
                    now=now,
                    started_at=runtime.started_at,
                    startup_grace=STARTUP_GRACE_SECONDS,
                    timeout=STALE_TIMEOUT_SECONDS,
                ):
                    runtime.stale_since = now
                    print(
                        f"Quelle {source_id}: kein Medienfortschritt "
                        f"seit mindestens {STALE_TIMEOUT_SECONDS:.0f}s; "
                        "FFmpeg wird neu gestartet.",
                        file=sys.stderr,
                        flush=True,
                    )
                    _signal_process(process, signal.SIGINT)
            if now - last_status_write >= 1.0:
                for runtime in processes.values():
                    runtime.sample_resources()
                    runtime.sample_timing_events(wall_now=time.time())
                status_store.write(_runtime_snapshot(
                    list(commands),
                    processes,
                    restart_at,
                    restart_states,
                    waiting_for_source,
                    now=now,
                ))
                last_status_write = now
            time.sleep(0.25)
    except (ConfigurationError, OSError, RuntimeError) as exc:
        print(
            f"Configuration error: {exc}",
            file=sys.stderr,
            flush=True,
        )
        stop_children()
        return 2
    finally:
        status_store.clear()
        deadline = time.monotonic() + 8
        for runtime in list(processes.values()):
            process = runtime.process
            remaining = max(0, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                process.kill()

    return 0


if __name__ == "__main__":
    sys.exit(main())
