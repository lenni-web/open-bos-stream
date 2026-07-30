"""Systemd-supervised multi-source FFmpeg runner."""

from __future__ import annotations

import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit, urlunsplit

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.stream.command import FFmpegCommandBuilder
from open_bos_stream.stream.exceptions import ConfigurationError


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
    commands: dict[str, list[str]] = {}
    processes: dict[str, subprocess.Popen] = {}
    restart_at: dict[str, float] = {}
    backoff: dict[str, float] = {}
    stopping = False

    def stop_children(*_: object) -> None:
        nonlocal stopping
        stopping = True
        for process in processes.values():
            if process.poll() is None:
                process.send_signal(signal.SIGINT)

    signal.signal(signal.SIGINT, stop_children)
    signal.signal(signal.SIGTERM, stop_children)

    try:
        for source in sources:
            command = builder.build_source(source)
            commands[source.id] = command
            backoff[source.id] = 1.0
            restart_at[source.id] = 0.0
            print("=" * 48, flush=True)
            print(
                f"Quelle {source.id}: {source.name} "
                f"({source.type}/{source.profile})",
                flush=True,
            )
            print(" ".join(_redact(item) for item in command), flush=True)

        while not stopping:
            now = time.monotonic()
            for source_id, command in commands.items():
                process = processes.get(source_id)
                if process is None:
                    if now < restart_at[source_id]:
                        continue
                    try:
                        processes[source_id] = subprocess.Popen(command)
                    except OSError as exc:
                        delay = backoff[source_id]
                        print(
                            f"Quelle {source_id} konnte nicht gestartet "
                            f"werden: {exc}; neuer Versuch in {delay:.0f}s.",
                            file=sys.stderr,
                            flush=True,
                        )
                        restart_at[source_id] = now + delay
                        backoff[source_id] = min(delay * 2, 30)
                    continue

                returncode = process.poll()
                if returncode is not None:
                    delay = backoff[source_id]
                    print(
                        f"Quelle {source_id} beendet "
                        f"(Exit {returncode}); neuer Versuch "
                        f"in {delay:.0f}s.",
                        file=sys.stderr,
                        flush=True,
                    )
                    processes.pop(source_id, None)
                    restart_at[source_id] = now + delay
                    backoff[source_id] = min(delay * 2, 30)
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
        deadline = time.monotonic() + 8
        for process in list(processes.values()):
            remaining = max(0, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                process.kill()

    return 0


if __name__ == "__main__":
    sys.exit(main())
