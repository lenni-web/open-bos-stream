"""Startet Chromium in der aktiven labwc/Wayland-Sitzung."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from open_bos_stream.core.config import ConfigLoader


def display_url(url: str, hide_cursor: bool) -> str:
    if not hide_cursor:
        return url

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query["display"] = "1"
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


def wayland_environment(timeout: float = 20.0) -> dict[str, str]:
    runtime_dir = Path(
        os.environ.get(
            "XDG_RUNTIME_DIR",
            f"/run/user/{os.getuid()}",
        )
    )
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        sockets = sorted(runtime_dir.glob("wayland-*"))
        sockets = [
            socket
            for socket in sockets
            if not socket.name.endswith(".lock")
        ]
        if sockets:
            environment = os.environ.copy()
            environment["XDG_RUNTIME_DIR"] = str(runtime_dir)
            environment["WAYLAND_DISPLAY"] = sockets[0].name
            environment.setdefault(
                "DBUS_SESSION_BUS_ADDRESS",
                f"unix:path={runtime_dir}/bus",
            )
            return environment

        time.sleep(0.5)

    raise RuntimeError(
        "Keine aktive labwc/Wayland-Sitzung gefunden."
    )


def chromium_command() -> list[str]:
    config = ConfigLoader().load().display
    chromium = (
        shutil.which("chromium")
        or shutil.which("chromium-browser")
    )
    if chromium is None:
        raise RuntimeError("Chromium ist nicht installiert.")

    if config.mode == "stream":
        url = config.stream_url
    else:
        url = config.dashboard_url

    command = [
        chromium,
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--ozone-platform=wayland",
        "--user-data-dir=/run/open-bos-display/chromium",
    ]

    if config.mode in {"kiosk", "stream"}:
        command.extend(
            [
                "--kiosk",
                "--noerrdialogs",
                "--disable-infobars",
            ]
        )
    elif config.fullscreen:
        command.append("--start-maximized")

    command.append(
        display_url(
            url,
            config.hide_cursor
            and config.mode != "normal",
        )
    )

    if config.disable_power_saving:
        inhibitor = shutil.which("systemd-inhibit")
        if inhibitor:
            command = [
                inhibitor,
                "--what=idle:sleep",
                "--who=Open BOS Display",
                "--why=Lokale Streamanzeige aktiv",
                "--mode=block",
                *command,
            ]

    return command


def main() -> int:
    try:
        environment = wayland_environment()
        command = chromium_command()
        print("Open BOS Display:", " ".join(command), flush=True)
        return subprocess.call(command, env=environment)
    except Exception as exc:
        print(f"Display error: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
