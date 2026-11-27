from __future__ import annotations

import time
from pathlib import Path

from open_bos_stream.core.event_log import ServerEventLog
from open_bos_stream.core.status_events import StatusEventTracker


def test_events_survive_restart_and_continue_numbering(tmp_path: Path) -> None:
    path = tmp_path / "event_log.jsonl"
    log = ServerEventLog(path)
    log.record("info", "Erster Eintrag")
    log.record("success", "Aufnahme gestartet", actor="einsatzleiter")

    restarted = ServerEventLog(path)
    feed = restarted.since(None)
    assert feed["instance"] == log.instance
    assert [event["message"] for event in feed["events"]] == [
        "Erster Eintrag",
        "Aufnahme gestartet · einsatzleiter",
    ]
    assert restarted.record("info", "Nach Neustart")["id"] == 3
    assert [event["id"] for event in restarted.since(2)["events"]] == [3]


def test_entries_older_than_30_days_are_removed(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "event_log.jsonl"
    now = time.time()
    monkeypatch.setattr(time, "time", lambda: now - 31 * 24 * 3600)
    ServerEventLog(path).record("info", "Uralt")
    monkeypatch.setattr(time, "time", lambda: now - 29 * 24 * 3600)
    ServerEventLog(path).record("info", "Noch gültig")
    monkeypatch.setattr(time, "time", lambda: now)

    log = ServerEventLog(path)
    assert [event["message"] for event in log.since(None)["events"]] == [
        "Noch gültig"
    ]
    assert "Uralt" not in path.read_text(encoding="utf-8")


def test_new_file_gets_new_instance(tmp_path: Path) -> None:
    first = ServerEventLog(tmp_path / "a.jsonl")
    second = ServerEventLog(tmp_path / "b.jsonl")
    assert first.instance != second.instance


def test_damaged_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "event_log.jsonl"
    log = ServerEventLog(path)
    log.record("info", "Gut")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("{kaputt\n")
    assert [e["message"] for e in ServerEventLog(path).since(None)["events"]] == ["Gut"]


def status(*, ready=True, mediamtx=True, storage="ok", failed=False, running=True):
    return {
        "services": {"mediamtx": {"online": mediamtx}},
        "sources": [{"id": "d1", "name": "Drohne 1", "ready": ready}],
        "media_storage": {"level": storage, "free_percent": 12.5},
        "stream_outputs": [{"name": "Owncast", "failed": failed}],
        "stream": {"controllable": True, "running": running},
    }


def test_status_tracker_reports_changes_once() -> None:
    tracker = StatusEventTracker()
    assert tracker.evaluate(status()) == [("success", "📡 1 von 1 Quellen online")]
    assert tracker.evaluate(status()) == []

    # Signalverlust erst nach zwei Prüfungen.
    assert tracker.evaluate(status(ready=False)) == []
    assert tracker.evaluate(status(ready=False)) == [
        ("warning", "🔴 Drohne 1: Signal verloren")
    ]
    assert tracker.evaluate(status(ready=True)) == [
        ("success", "🟢 Drohne 1: Signal verfügbar")
    ]

    events = tracker.evaluate(
        status(mediamtx=False, storage="warning", failed=True, running=False)
    )
    assert ("error", "📡 Streaming-Server nicht erreichbar") in events
    assert ("warning", "💾 Speicher wird knapp (12,5 % frei)") in events
    assert ("error", "📺 Weiterleitung „Owncast“ unerwartet beendet") in events
    assert ("warning", "🔴 Streamer gestoppt") in events


def test_short_dropout_does_not_flood_the_log() -> None:
    tracker = StatusEventTracker()
    tracker.evaluate(status())
    assert tracker.evaluate(status(ready=False)) == []
    assert tracker.evaluate(status(ready=True)) == []


def test_recording_events_name_source_and_user(tmp_path: Path) -> None:
    from test_media_capture import (
        FakeMediaMTX,
        FakeRecorder,
        FakeRecordingManager,
        selected_second_source,
    )
    from open_bos_stream.recording.service import RecordingService

    config, source = selected_second_source()
    log = ServerEventLog(None)
    service = RecordingService(
        config,
        FakeMediaMTX(),
        manager_factory=FakeRecordingManager,
        event_log=log,
    )
    service._recorder = FakeRecorder(tmp_path)

    service.start(actor="einsatzleiter")
    service.stop(actor="einsatzleiter")

    messages = [event["message"] for event in log.since(None)["events"]]
    assert messages[0] == f"⏺ Aufnahme gestartet · {source.name} · einsatzleiter"
    assert messages[1] == f"⏹ Aufnahme beendet · {source.name} · einsatzleiter"


def test_dashboard_delivers_only_new_events_to_superadmins(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from open_bos_stream.api import dashboard as dashboard_api
    from open_bos_stream.core.container import auth_service, dashboard_service
    from open_bos_stream.main import app

    log = ServerEventLog(None)
    for index in range(3):
        log.record("info", f"Eintrag {index + 1}")
    monkeypatch.setattr(dashboard_api, "server_event_log", log)
    monkeypatch.setattr(dashboard_service, "status", lambda: {"sources": []})
    monkeypatch.setattr(
        auth_service,
        "verify_token",
        lambda token, *, purpose="session": (
            {"username": token, "role": token}
            if token in {"viewer", "admin", "superadmin"}
            else None
        ),
    )
    monkeypatch.setattr(type(auth_service), "configured", property(lambda self: True))
    client = TestClient(app)

    client.cookies.set(auth_service.COOKIE_NAME, "superadmin")
    first = client.get("/dashboard/status").json()["server_events"]
    assert [event["id"] for event in first["events"]] == [1, 2, 3]
    later = client.get("/dashboard/status?events_after=2").json()["server_events"]
    assert [event["id"] for event in later["events"]] == [3]

    # Seit 0.25.4 nur noch für Superadmins.
    for role in ("viewer", "admin"):
        client.cookies.set(auth_service.COOKIE_NAME, role)
        assert "server_events" not in client.get("/dashboard/status").json()
