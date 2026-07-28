from dataclasses import dataclass


@dataclass(slots=True)
class DisplayConfig:

    enabled: bool = False

    mode: str = "kiosk"

    browser: str = "chromium"

    url: str = "http://127.0.0.1:8080"

    fullscreen: bool = True

    cursor: bool = False
