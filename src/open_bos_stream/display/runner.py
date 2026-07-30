"""Startet eine lokale labwc-Sitzung mit Chromium."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import signal
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


def wayland_environment(
    timeout: float = 20.0,
    compositor: subprocess.Popen | None = None,
) -> dict[str, str]:
    runtime_dir = Path(
        os.environ.get(
            "XDG_RUNTIME_DIR",
            f"/run/user/{os.getuid()}",
        )
    )
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if compositor is not None:
            returncode = compositor.poll()
            if returncode is not None:
                raise RuntimeError(
                    "labwc wurde vor dem Aufbau der "
                    f"Wayland-Sitzung beendet (Exit {returncode})."
                )

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
        "labwc hat innerhalb von "
        f"{timeout:g} Sekunden keinen Wayland-Socket angelegt."
    )


def chromium_command(
    runtime_dir: str = "/run/open-bos-display",
) -> list[str]:
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
        f"--user-data-dir={runtime_dir}/chromium",
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

    return command


def compositor_command() -> list[str]:
    labwc = shutil.which("labwc")
    if labwc is None:
        raise RuntimeError(
            "labwc ist nicht installiert. Bitte das Update-Skript "
            "erneut ausführen."
        )
    return [labwc]


def base_environment() -> dict[str, str]:
    environment = os.environ.copy()
    runtime_dir = Path(
        environment.get(
            "XDG_RUNTIME_DIR",
            "/run/open-bos-display",
        )
    )
    runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    runtime_dir.chmod(0o700)

    environment["XDG_RUNTIME_DIR"] = str(runtime_dir)
    environment["XDG_SESSION_TYPE"] = "wayland"
    environment["XDG_CURRENT_DESKTOP"] = "labwc"
    environment.setdefault("WLR_LIBINPUT_NO_DEVICES", "1")
    return environment


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def run_display_session() -> int:
    environment = base_environment()
    labwc_command = compositor_command()

    print(
        "Open BOS Display compositor:",
        " ".join(labwc_command),
        flush=True,
    )
    compositor = subprocess.Popen(
        labwc_command,
        env=environment,
    )
    browser: subprocess.Popen | None = None

    try:
        environment = wayland_environment(
            timeout=20,
            compositor=compositor,
        )
        command = chromium_command(
            environment["XDG_RUNTIME_DIR"],
        )
        print("Open BOS Display browser:", " ".join(command), flush=True)
        browser = subprocess.Popen(command, env=environment)

        while True:
            browser_returncode = browser.poll()
            if browser_returncode is not None:
                return browser_returncode

            compositor_returncode = compositor.poll()
            if compositor_returncode is not None:
                raise RuntimeError(
                    "labwc wurde während der Anzeige beendet "
                    f"(Exit {compositor_returncode})."
                )

            time.sleep(0.5)
    finally:
        stop_process(browser)
        stop_process(compositor)


def main() -> int:
    try:
        signal.signal(signal.SIGTERM, signal.default_int_handler)
        signal.signal(signal.SIGINT, signal.default_int_handler)
        return run_display_session()
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Display error: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
