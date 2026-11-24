from __future__ import annotations

import time
from datetime import datetime

from open_bos_stream.core import timezone


def test_default_timezone_is_german_time(monkeypatch) -> None:
    monkeypatch.delenv("OPEN_BOS_TIMEZONE", raising=False)
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()

    assert timezone.apply_timezone() == "Europe/Berlin"
    # 24.11.2026 10:00 UTC ist Winterzeit (MEZ, UTC+1).
    winter = datetime.fromtimestamp(1795514400)
    assert winter.strftime("%H:%M") == "11:00"
    # 15.07.2026 10:00 UTC ist Sommerzeit (MESZ, UTC+2).
    summer = datetime.fromtimestamp(1784109600)
    assert summer.strftime("%H:%M") == "12:00"


def test_timezone_can_be_overridden(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_BOS_TIMEZONE", "Europe/London")
    assert timezone.apply_timezone() == "Europe/London"
    assert datetime.fromtimestamp(1795514400).strftime("%H:%M") == "10:00"


def test_unknown_timezone_keeps_system_setting(monkeypatch) -> None:
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    monkeypatch.setenv("OPEN_BOS_TIMEZONE", "Mond/Basis")
    assert timezone.apply_timezone() is None
    assert datetime.fromtimestamp(1795514400).strftime("%H:%M") == "10:00"


def teardown_module() -> None:
    # Andere Tests nicht beeinflussen: deutsche Zeit wie im Betrieb.
    import os

    os.environ.pop("OPEN_BOS_TIMEZONE", None)
    timezone.apply_timezone()
