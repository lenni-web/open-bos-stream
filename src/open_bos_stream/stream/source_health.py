"""Gemeinsame Gesundheitsbewertung einer Streamquelle."""

from __future__ import annotations

import time
from typing import Any, Mapping


HEALTH_LABELS = {
    "stable": "Stabil",
    "offline": "Offline",
    "connecting": "Verbindet",
    "recovering": "Wird wiederhergestellt",
    "restart_loop": "Neustartschleife",
    "stalled": "Stream hängt",
    "under_load": "Verarbeitung zu langsam",
    "timing_issue": "Bildfolge auffällig",
    "unknown": "Keine Laufzeitdaten",
}


def source_health(
    *,
    ready: bool,
    online: bool,
    managed: bool,
    runtime: Mapping[str, Any] | None,
    now: float | None = None,
) -> dict[str, str]:
    """Verdichtet Signal und Laufzeitwerte zu einem stabilen UI-Vertrag."""

    timestamp = time.time() if now is None else now
    code = "stable" if ready else "offline"
    message = "Quelle liefert ein ausgabefähiges Signal."

    if not managed:
        if not ready:
            message = (
                "MediaMTX wartet auf einen Publisher."
                if not online
                else "Eingangssignal ist noch nicht ausgabefähig."
            )
        return _result(code, message)

    if runtime is None:
        return _result(
            "unknown" if ready else "offline",
            "FFmpeg-Laufzeitdaten sind momentan nicht verfügbar.",
        )

    state = str(runtime.get("state", "unknown"))
    restarts = int(runtime.get("restart_count", 0) or 0)
    last_restart_at = _number(runtime.get("last_restart_at"))
    restart_recent = (
        last_restart_at is not None
        and timestamp - last_restart_at <= 120
    )
    reason = str(runtime.get("last_restart_reason") or "")

    if restarts >= 3 and restart_recent:
        return _result(
            "restart_loop",
            f"FFmpeg wurde in kurzer Zeit {restarts}-mal neu gestartet.",
        )
    if state == "restarting" and reason == "stale":
        return _result(
            "stalled",
            "FFmpeg läuft, meldet aber keinen Medienfortschritt.",
        )
    if state in {"restarting", "waiting_restart"}:
        return _result(
            "recovering",
            "Die Quelle wird automatisch neu verbunden.",
        )
    if not ready:
        return _result(
            "connecting" if state in {"starting", "running"} else "offline",
            "FFmpeg läuft, die Ausgabe ist aber noch nicht bereit.",
        )

    speed = _number(runtime.get("speed")) or 0.0
    if 0 < speed < 0.9:
        return _result(
            "under_load",
            f"FFmpeg verarbeitet nur mit {speed:.2f}× Echtzeit.",
        )

    last_timing_issue = max(
        _number(runtime.get("last_drop_at")) or 0.0,
        _number(runtime.get("last_dup_at")) or 0.0,
    )
    if last_timing_issue and timestamp - last_timing_issue <= 15:
        return _result(
            "timing_issue",
            "FFmpeg hat kürzlich Frames verworfen oder dupliziert.",
        )

    return _result("stable", message)


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _result(code: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "label": HEALTH_LABELS[code],
        "message": message,
    }
