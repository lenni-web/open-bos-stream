"""Konfiguration des lokal angeschlossenen Displays."""

from typing import Literal

from pydantic import BaseModel


class DisplayConfig(BaseModel):
    enabled: bool = False
    mode: Literal["kiosk", "normal", "stream"] = "kiosk"
    browser: Literal["chromium"] = "chromium"
    dashboard_url: str = "http://127.0.0.1:8000"
    stream_url: str = "http://127.0.0.1:8000/display/stream"
    fullscreen: bool = True
    hide_cursor: bool = True
    disable_power_saving: bool = True
