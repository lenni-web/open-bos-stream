from pathlib import Path

import pytest
from pydantic import ValidationError

from open_bos_stream.display.config import DisplayConfig
from open_bos_stream.display.runner import (
    base_environment,
    chromium_command,
    display_url,
    redact_ticket,
    wayland_environment,
    with_ticket,
)
from open_bos_stream.display.ticket import issue_ticket, ticket_valid


def test_display_modes_are_explicit() -> None:
    for mode in ("kiosk", "normal", "stream"):
        assert DisplayConfig(mode=mode).mode == mode

    with pytest.raises(ValidationError):
        DisplayConfig(mode="unknown")


def test_display_url_adds_cursor_marker() -> None:
    assert display_url(
        "http://127.0.0.1:8000/?page=dashboard",
        True,
    ) == (
        "http://127.0.0.1:8000/"
        "?page=dashboard&display=1"
    )

    assert display_url(
        "http://127.0.0.1:8000",
        False,
    ) == "http://127.0.0.1:8000"


def test_wayland_environment_detects_labwc_socket(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "wayland-0").touch()
    monkeypatch.setenv(
        "XDG_RUNTIME_DIR",
        str(tmp_path),
    )
    monkeypatch.delenv(
        "WAYLAND_DISPLAY",
        raising=False,
    )

    environment = wayland_environment(timeout=0.1)

    assert environment["XDG_RUNTIME_DIR"] == str(tmp_path)
    assert environment["WAYLAND_DISPLAY"] == "wayland-0"


def test_base_environment_prepares_private_runtime_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_dir = tmp_path / "display-runtime"
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)

    environment = base_environment()

    assert runtime_dir.is_dir()
    assert runtime_dir.stat().st_mode & 0o777 == 0o700
    assert environment["XDG_SESSION_TYPE"] == "wayland"
    assert environment["XDG_CURRENT_DESKTOP"] == "labwc"


def test_chromium_starts_without_privileged_inhibitor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "OPEN_BOS_DISPLAY_TICKET_FILE",
        str(tmp_path / "kiosk-ticket"),
    )
    monkeypatch.setattr(
        "open_bos_stream.display.runner.shutil.which",
        lambda command: f"/usr/bin/{command}",
    )
    monkeypatch.setattr(
        "open_bos_stream.display.runner.ConfigLoader.load",
        lambda _loader: type(
            "Config",
            (),
            {
                "display": DisplayConfig(
                    disable_power_saving=True,
                )
            },
        )(),
    )

    command = chromium_command()

    assert command[0] == "/usr/bin/chromium"
    assert "systemd-inhibit" not in command


def test_kiosk_url_carries_secret_ticket_and_log_redacts_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket_path = tmp_path / "kiosk-ticket"
    monkeypatch.setenv("OPEN_BOS_DISPLAY_TICKET_FILE", str(ticket_path))
    monkeypatch.setattr(
        "open_bos_stream.display.runner.shutil.which",
        lambda command: f"/usr/bin/{command}",
    )
    monkeypatch.setattr(
        "open_bos_stream.display.runner.ConfigLoader.load",
        lambda _loader: type(
            "Config",
            (),
            {"display": DisplayConfig(mode="kiosk")},
        )(),
    )

    command = chromium_command()
    ticket = ticket_path.read_text(encoding="utf-8")

    assert ticket_path.stat().st_mode & 0o777 == 0o600
    assert ticket_valid(ticket)
    assert f"display_ticket={ticket}" in command[-1]
    assert ticket not in " ".join(redact_ticket(command))
    assert "display_ticket=***" in " ".join(redact_ticket(command))


def test_display_ticket_rejects_missing_or_wrong_values(
    tmp_path: Path,
) -> None:
    ticket_path = tmp_path / "kiosk-ticket"

    assert not ticket_valid("irgendwas", ticket_path)

    ticket = issue_ticket(ticket_path)

    assert ticket_valid(ticket, ticket_path)
    assert not ticket_valid(None, ticket_path)
    assert not ticket_valid("", ticket_path)
    assert not ticket_valid(ticket + "x", ticket_path)
    assert with_ticket("http://127.0.0.1:8000/", ticket) == (
        "http://127.0.0.1:8000/"
    )
