from __future__ import annotations

import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from open_bos_stream.core.models import AppConfig, NotificationConfig
from open_bos_stream.notifications.mailer import (
    MailDeliveryError,
    build_message,
    send_mail,
)
from open_bos_stream.notifications.monitor import (
    NotificationMonitor,
    Notice,
    mask_stream_urls,
)
from open_bos_stream.notifications.service import NotificationService


def status(
    *,
    mediamtx: bool = True,
    sources: list[dict] | None = None,
    storage: str = "ok",
    recording: dict | None = None,
    outputs: list[dict] | None = None,
) -> dict:
    return {
        "services": {"mediamtx": {"online": mediamtx}},
        "sources": sources or [],
        "media_storage": {"level": storage, "free_percent": 12.5},
        "recording": recording or {},
        "stream_outputs": outputs or [],
    }


def drone(online: bool) -> dict:
    return {"id": "drohne", "name": "Drohne Agathenburg", "online": online}


def started_monitor(initial: dict | None = None) -> NotificationMonitor:
    monitor = NotificationMonitor()
    first = monitor.evaluate(initial or status(), 0)
    assert [notice.event for notice in first] == ["server_started"]
    return monitor


# ----------------------------------------------------------------------
# Überwachung
# ----------------------------------------------------------------------


def test_source_alert_waits_for_delay_and_sends_recovery() -> None:
    monitor = started_monitor(status(sources=[drone(True)]))

    assert monitor.evaluate(status(sources=[drone(False)]), 10) == []
    assert monitor.evaluate(status(sources=[drone(False)]), 30) == []
    alert = monitor.evaluate(status(sources=[drone(False)]), 41)
    assert len(alert) == 1
    assert alert[0].event == "source_offline"
    assert "Drohne Agathenburg" in alert[0].subject
    # Keine Wiederholung, solange die Störung anhält.
    assert monitor.evaluate(status(sources=[drone(False)]), 300) == []

    recovery = monitor.evaluate(status(sources=[drone(True)]), 310)
    assert len(recovery) == 1 and recovery[0].recovery


def test_short_source_dropout_is_not_reported() -> None:
    monitor = started_monitor(status(sources=[drone(True)]))

    assert monitor.evaluate(status(sources=[drone(False)]), 5) == []
    assert monitor.evaluate(status(sources=[drone(True)]), 20) == []
    assert monitor.evaluate(status(sources=[drone(False)]), 25) == []
    assert monitor.evaluate(status(sources=[drone(False)]), 50) == []


def test_source_that_never_sent_is_not_a_fault() -> None:
    monitor = started_monitor(status(sources=[drone(False)]))

    assert monitor.evaluate(status(sources=[drone(False)]), 600) == []


def test_repeated_source_alerts_respect_cooldown() -> None:
    monitor = started_monitor(status(sources=[drone(True)]))
    monitor.evaluate(status(sources=[drone(False)]), 1)
    assert monitor.evaluate(status(sources=[drone(False)]), 40)
    assert monitor.evaluate(status(sources=[drone(True)]), 50)

    # Erneuter Ausfall innerhalb von zehn Minuten: keine zweite Mail und
    # deshalb auch keine Entwarnung.
    monitor.evaluate(status(sources=[drone(False)]), 60)
    assert monitor.evaluate(status(sources=[drone(False)]), 100) == []
    assert monitor.evaluate(status(sources=[drone(True)]), 110) == []

    monitor.evaluate(status(sources=[drone(False)]), 700)
    assert monitor.evaluate(status(sources=[drone(False)]), 740)


def test_mediamtx_outage_and_recovery() -> None:
    monitor = started_monitor()

    assert monitor.evaluate(status(mediamtx=False), 10) == []
    alert = monitor.evaluate(status(mediamtx=False), 31)
    assert [notice.event for notice in alert] == ["mediamtx_offline"]
    recovery = monitor.evaluate(status(mediamtx=True), 40)
    assert recovery[0].recovery


def test_storage_warning_escalation_and_recovery() -> None:
    monitor = started_monitor()

    warning = monitor.evaluate(status(storage="warning"), 10)
    assert warning[0].subject == "Warnung: Speicher wird knapp"
    assert "12,5 %" in warning[0].body
    assert monitor.evaluate(status(storage="warning"), 20) == []
    critical = monitor.evaluate(status(storage="critical"), 30)
    assert critical[0].subject == "Störung: Speicher erschöpft"
    recovery = monitor.evaluate(status(storage="ok"), 40)
    assert recovery[0].recovery


def test_recording_problems_are_reported_once() -> None:
    old = {"finished_at": 1.0, "end_reason": "failed"}
    monitor = started_monitor(status(recording=old))
    # Vor dem Start beendete Aufnahmen werden nicht nachgemeldet.
    assert monitor.evaluate(status(recording=old), 5) == []

    interrupted = {
        "finished_at": 2.0,
        "end_reason": "stream_interrupted",
        "source_name": "Drohne",
        "completed_filename": "aufnahme.mp4",
    }
    notices = monitor.evaluate(status(recording=interrupted), 10)
    assert [notice.event for notice in notices] == ["recording_problem"]
    assert "aufnahme.mp4" in notices[0].body
    assert monitor.evaluate(status(recording=interrupted), 15) == []

    completed = {"finished_at": 3.0, "end_reason": "completed"}
    assert monitor.evaluate(status(recording=completed), 20) == []


def test_output_failure_is_reported_but_manual_stop_is_not() -> None:
    running = {"name": "Owncast", "running": True, "failed": False}
    monitor = started_monitor(status(outputs=[running]))

    stopped = {"name": "Owncast", "running": False, "failed": False,
               "error": "ffmpeg banner"}
    assert monitor.evaluate(status(outputs=[stopped]), 10) == []

    monitor.evaluate(status(outputs=[running]), 20)
    failed = {
        "name": "Owncast",
        "running": False,
        "failed": True,
        "error": "rtmp://owncast.example:1935/live/GEHEIM: Broken pipe",
    }
    notices = monitor.evaluate(status(outputs=[failed]), 30)
    assert [notice.event for notice in notices] == ["output_failed"]
    assert "GEHEIM" not in notices[0].body
    assert "rtmp://owncast.example:1935/***" in notices[0].body
    recovery = monitor.evaluate(status(outputs=[running]), 40)
    assert recovery[0].recovery


def test_stream_urls_are_masked() -> None:
    text = "srt://user:pw@10.0.0.1:9000?streamid=abc und https://x.de/k?t=1"
    masked = mask_stream_urls(text)
    assert "pw" not in masked and "abc" not in masked and "t=1" not in masked
    assert "srt://10.0.0.1:9000/***" in masked


# ----------------------------------------------------------------------
# Konfiguration und Versand
# ----------------------------------------------------------------------


def mail_config(**overrides) -> NotificationConfig:
    values = {
        "enabled": True,
        "smtp_host": "smtp.example.org",
        "sender": "stream@example.org",
        "recipients": ["leitung@example.org"],
        "username": "stream@example.org",
    }
    values.update(overrides)
    return NotificationConfig(**values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"smtp_host": ""},
        {"recipients": []},
        {"recipients": ["kein-mail"]},
        {"sender": "a@b.de\nBcc: fremd@example.org"},
    ],
)
def test_invalid_notification_settings_are_rejected(overrides) -> None:
    with pytest.raises(ValueError):
        mail_config(**overrides)


def test_message_headers_cannot_be_injected_via_subject() -> None:
    message = build_message(
        mail_config(),
        "Quelle „X“\r\nBcc: fremd@example.org",
        "Text",
    )
    assert "\n" not in message["Subject"]
    assert message["Bcc"] is None


class FakeSMTP:
    def __init__(self) -> None:
        self.calls: list = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, message):
        self.calls.append(("send", message["To"], message["Subject"]))


def test_send_mail_uses_starttls_and_login() -> None:
    client = FakeSMTP()
    send_mail(
        mail_config(),
        "geheim",
        "Betreff",
        "Text",
        smtp_factory=lambda config: client,
    )
    assert client.calls[0] == "starttls"
    assert client.calls[1] == ("login", "stream@example.org", "geheim")
    assert client.calls[2] == ("send", "leitung@example.org", "Betreff")


def test_unreachable_smtp_server_raises_readable_error() -> None:
    def refuse(config):
        raise ConnectionRefusedError(61, "Connection refused")

    with pytest.raises(MailDeliveryError, match="nicht erreichbar"):
        send_mail(mail_config(), "", "B", "T", smtp_factory=refuse)


def test_service_respects_switches_and_stores_password_privately(
    tmp_path: Path,
) -> None:
    sent = []
    config = AppConfig.model_validate(
        {
            **_minimal_app_config(),
            "notifications": mail_config(
                events={"server_started": False}
            ).model_dump(),
        }
    )
    service = NotificationService(
        config,
        secret_file=tmp_path / "notifications.secret",
        sender=lambda settings, password, subject, body: sent.append(
            (password, subject, body)
        ),
    )

    service.set_password("smtp-geheim")
    mode = stat.S_IMODE((tmp_path / "notifications.secret").stat().st_mode)
    assert mode == 0o600
    assert service.password_set
    service.set_password(None)  # leer: bisheriges Passwort bleibt
    assert service.password() == "smtp-geheim"

    assert not service.enqueue(
        Notice(event="server_started", subject="Start", body="")
    )
    assert service.enqueue(
        Notice(event="source_offline", subject="Quelle weg", body="Text")
    )
    service._queue.join()
    assert sent[0][0] == "smtp-geheim"
    assert "Quelle weg" in sent[0][1]
    assert "Version" in sent[0][2]

    config.notifications.enabled = False
    assert not service.enqueue(
        Notice(event="source_offline", subject="Quelle weg", body="Text")
    )

    service.set_password(None, clear=True)
    assert not service.password_set


def _minimal_app_config() -> dict:
    import yaml

    fixture = Path(__file__).parent / "fixtures" / "stream.yaml"
    return yaml.safe_load(fixture.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------
# Schnittstelle
# ----------------------------------------------------------------------


@pytest.fixture
def superadmin_client(monkeypatch, tmp_path):
    from open_bos_stream.core.container import (
        auth_service,
        notification_service,
    )
    from open_bos_stream.main import app

    def fake_verify(token, *, purpose="session"):
        if purpose == "session" and token in {"viewer", "admin", "superadmin"}:
            return {"username": token, "role": token}
        return None

    monkeypatch.setattr(auth_service, "verify_token", fake_verify)
    monkeypatch.setattr(
        type(auth_service), "configured", property(lambda self: True)
    )
    monkeypatch.setattr(
        notification_service,
        "_secret_file",
        tmp_path / "notifications.secret",
    )
    client = TestClient(app)
    client.cookies.set(auth_service.COOKIE_NAME, "superadmin")
    yield client
    # Gemeinsame Testkonfiguration wieder auf den Ausgangszustand setzen.
    client.cookies.set(auth_service.COOKIE_NAME, "superadmin")
    client.put(
        "/config/notifications",
        json={**NotificationConfig().model_dump(), "clear_password": True},
    )


def test_notification_api_never_returns_password(superadmin_client) -> None:
    payload = mail_config().model_dump()
    response = superadmin_client.put(
        "/config/notifications",
        json={**payload, "password": "smtp-geheim"},
    )
    assert response.status_code == 200, response.text
    body = response.json()["notifications"]
    assert body["password_set"] is True
    assert "smtp-geheim" not in response.text

    loaded = superadmin_client.get("/config/notifications")
    assert "smtp-geheim" not in loaded.text
    assert loaded.json()["recipients"] == ["leitung@example.org"]

    # Ein späterer Speichervorgang ohne Passwort behält das gespeicherte.
    superadmin_client.put("/config/notifications", json=payload)
    assert superadmin_client.get(
        "/config/notifications"
    ).json()["password_set"] is True

    # Allgemeines Speichern der Konfiguration überschreibt die
    # Benachrichtigungen nicht mit einem veralteten Browserstand.
    config = superadmin_client.get("/config/").json()
    config["notifications"] = NotificationConfig().model_dump()
    from open_bos_stream.api import config as config_api

    captured = {}

    async def fake_apply(candidate):
        captured["notifications"] = candidate.notifications
        return {"success": True}

    original = config_api.apply_config
    config_api.apply_config = fake_apply
    try:
        superadmin_client.put("/config/", json=config)
    finally:
        config_api.apply_config = original
    assert captured["notifications"].recipients == ["leitung@example.org"]


def test_admin_config_view_hides_mail_settings(superadmin_client) -> None:
    from open_bos_stream.core.container import auth_service

    superadmin_client.put(
        "/config/notifications",
        json=mail_config().model_dump(),
    )
    superadmin_client.cookies.set(auth_service.COOKIE_NAME, "admin")
    notifications = superadmin_client.get("/config/").json()["notifications"]
    assert notifications["recipients"] == []
    assert notifications["smtp_host"] == ""
    assert superadmin_client.get(
        "/config/notifications"
    ).status_code == 403


def test_test_mail_errors_are_reported(superadmin_client, monkeypatch) -> None:
    from open_bos_stream.core.container import notification_service

    superadmin_client.put(
        "/config/notifications",
        json=mail_config().model_dump(),
    )

    def fail(settings, password, subject, body):
        raise MailDeliveryError("SMTP-Server smtp.example.org:587 nicht erreichbar")

    monkeypatch.setattr(notification_service, "_send", fail)
    response = superadmin_client.post("/config/notifications/test")
    assert response.status_code == 502
    assert "nicht erreichbar" in response.json()["detail"]
    assert notification_service.status()["success"] is False
