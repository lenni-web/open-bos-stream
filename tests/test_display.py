from pathlib import Path

import pytest
from pydantic import ValidationError

from open_bos_stream.display.config import DisplayConfig
from open_bos_stream.display.runner import (
    display_url,
    wayland_environment,
)


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
