from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from open_bos_stream.auth.guest_access import can_see_source
from open_bos_stream.auth.guest_links import GuestLinkStore
from open_bos_stream.incidents.service import IncidentAccessError, IncidentError
from open_bos_stream.notifications.monitor import Notice
from open_bos_stream.notifications.push_service import PushService
from open_bos_stream.org.service import OrgError
from tests.test_organizations import PASSWORD, auth, build, session, source  # noqa: F401


@pytest.fixture
def setup(auth):  # noqa: F811
    ids = build(auth)
    return SimpleNamespace(auth=auth, ids=ids, incidents=auth.incidents)


def create(setup, username: str = "b-team", **extra):
    values = {"lead_organization_id": setup.ids["b"], "alarm_at": "2026-11-26T14:32", "keyword": "TH Person vermisst"}
    values.update(extra)
    return setup.incidents.create(session(setup.auth, username), **values)


# ----------------------------------------------------------------------
# Kennung
# ----------------------------------------------------------------------


def test_code_is_date_and_alarm_time_with_suffix_on_collision(setup) -> None:
    first = create(setup)
    second = create(setup)
    assert first["code"] == "2026-11-26-1432"
    assert second["code"] == "2026-11-26-1432-2"

    changed = setup.incidents.update(session(setup.auth, "b-team"), second["id"], alarm_at="2026-11-26T15:05")
    assert changed["code"] == "2026-11-26-1505"
    assert any("Alarmzeit" in entry["text"] for entry in setup.incidents.log(second["id"]))


# ----------------------------------------------------------------------
# Rechte
# ----------------------------------------------------------------------


def test_only_drone_team_of_the_lead_may_create(setup) -> None:
    with pytest.raises(IncidentAccessError):
        create(setup, "b-zuschauer")
    with pytest.raises(IncidentAccessError):
        create(setup, "a-admin")  # andere Wehr
    assert create(setup, "kreis")["lead_organization_id"] == setup.ids["b"]


def test_involved_wehren_see_and_edit_the_incident(setup) -> None:
    incident = create(setup)
    a_admin = session(setup.auth, "a-admin")
    viewer = session(setup.auth, "b-zuschauer")

    assert setup.incidents.can_view(viewer, incident)
    assert not setup.incidents.can_edit(viewer, incident)
    assert not setup.incidents.can_view(a_admin, incident)
    assert setup.incidents.can_view(session(setup.auth, "kreis"), incident)

    incident = setup.incidents.add_organization(session(setup.auth, "b-team"), incident["id"], setup.ids["a"])
    assert setup.incidents.can_view(a_admin, incident)
    assert setup.incidents.can_edit(a_admin, incident)
    # Beteiligte dürfen nicht abschließen oder löschen.
    assert not setup.incidents.can_administer(a_admin, incident)
    assert [item["id"] for item in setup.incidents.visible(a_admin)] == [incident["id"]]


def test_closed_incident_is_edited_only_by_lead_admins(setup) -> None:
    incident = create(setup)
    team = session(setup.auth, "b-team")
    setup.incidents.set_status(team, incident["id"], "ended")
    with pytest.raises(IncidentAccessError):
        setup.incidents.set_status(team, incident["id"], "closed")
    closed = setup.incidents.set_status(session(setup.auth, "kreis"), incident["id"], "closed")
    assert closed["status"] == "closed" and closed["ended_at"]
    with pytest.raises(IncidentAccessError):
        setup.incidents.add_note(team, incident["id"], "Nachtrag")


def test_organization_with_incidents_cannot_be_deleted(setup) -> None:
    org = setup.auth.ready()
    extra = org.create_organization(name="OF C", kind="ortsfeuerwehr", parent_id=1)["id"]
    incident = create(setup)
    setup.incidents.add_organization(session(setup.auth, "b-team"), incident["id"], extra)
    with pytest.raises(OrgError, match="archivieren"):
        org.delete_organization(extra)


# ----------------------------------------------------------------------
# Drohnen anderer Wehren im gemeinsamen Einsatz
# ----------------------------------------------------------------------


def test_involved_wehr_sees_foreign_drone_only_while_incident_runs(setup) -> None:
    drone = source("b1", setup.ids["b"])
    team = session(setup.auth, "b-team")
    incident = create(setup)
    setup.incidents.add_source(team, incident["id"], drone)

    assert not can_see_source(session(setup.auth, "a-admin"), drone)
    setup.incidents.add_organization(team, incident["id"], setup.ids["a"])
    a_admin = session(setup.auth, "a-admin")
    assert a_admin["incident_source_ids"] == ["b1"]
    assert can_see_source(a_admin, drone)

    setup.incidents.set_status(team, incident["id"], "ended")
    assert not can_see_source(session(setup.auth, "a-admin"), drone)
    assert setup.incidents.sources(incident["id"])[0]["removed_at"]


def test_recording_sources_follow_running_incidents(setup) -> None:
    service = setup.incidents
    assert service.recording_source_ids() == set()
    incident = create(setup)
    user = session(setup.auth, "b-team")
    service.add_source(user, incident["id"], source("b1", setup.ids["b"]))
    assert service.recording_source_ids() == {"b1"}
    service.set_status(user, incident["id"], "ended")
    assert service.recording_source_ids() == set()


def test_incident_media_matches_drones_and_time_window(setup) -> None:
    team = session(setup.auth, "b-team")
    incident = create(setup, alarm_at="2026-11-26T14:00")
    setup.incidents.add_source(team, incident["id"], source("b1", setup.ids["b"]))
    stamp = setup.incidents.sources(incident["id"])[0]["added_at"]
    from datetime import datetime, timedelta

    added = datetime.fromisoformat(stamp)
    inside = (added + timedelta(seconds=30)).strftime("%Y%m%d_%H%M%S")
    before = (added - timedelta(hours=2)).strftime("%Y%m%d_%H%M%S")
    items = [
        {"type": "snapshot", "name": f"snapshot_b1_{inside}.jpg", "size": 1, "modified": 0, "protected": False},
        {"type": "recording", "name": f"recording_b1_{before}.mp4", "size": 1, "modified": 0, "protected": False},
        {"type": "recording", "name": f"recording_andere_{inside}.mp4", "size": 1, "modified": 0, "protected": False},
    ]
    media = setup.incidents.media(setup.incidents.get(incident["id"]), items)
    assert [item["name"] for item in media] == [f"snapshot_b1_{inside}.jpg"]


# ----------------------------------------------------------------------
# Personen
# ----------------------------------------------------------------------


def test_participants_with_and_without_account(setup) -> None:
    team = session(setup.auth, "b-team")
    incident = create(setup)
    candidates = {item["name"] for item in setup.incidents.candidates(incident)}
    assert "b-zuschauer" in candidates and "a-admin" not in candidates

    viewer_id = session(setup.auth, "b-zuschauer")["user_id"]
    pilot = setup.incidents.add_participant(team, incident["id"], role="fernpilot", user_id=viewer_id)
    assert pilot["warning"] == "Kein gültiger Fernpilotennachweis hinterlegt."

    setup.auth.ready().add_qualification(viewer_id, kind="a2")
    assert setup.incidents.participants(incident["id"])[0]["warning"] == ""

    guest = setup.incidents.add_participant(team, incident["id"], role="luftraumbeobachter", name="Max Muster")
    assert guest["user_id"] is None and guest["name"] == "Max Muster"

    foreign = session(setup.auth, "a-admin")["user_id"]
    with pytest.raises(IncidentError):
        setup.incidents.add_participant(team, incident["id"], role="fernpilot", user_id=foreign)


# ----------------------------------------------------------------------
# Einsatz-Gastlinks und Push
# ----------------------------------------------------------------------


def test_incident_guest_link_follows_drones_and_ends_with_incident(setup, tmp_path: Path) -> None:
    store = GuestLinkStore(tmp_path / "guest_links.json")
    setup.auth.guest_links = store
    team = session(setup.auth, "b-team")
    incident = create(setup)
    link, _token = store.create(label="Leitstelle", source_ids=[], hours=4, created_by="b-team", incident_id=incident["id"])
    guest_token = setup.auth.create_guest_token(link)

    assert setup.auth.verify_token(guest_token)["source_ids"] == []
    setup.incidents.add_source(team, incident["id"], source("b1", setup.ids["b"]))
    guest = setup.auth.verify_token(guest_token)
    assert guest["source_ids"] == ["b1"] and guest["incident_id"] == incident["id"]

    setup.incidents.set_status(team, incident["id"], "ended")
    assert setup.auth.verify_token(guest_token) is None


def test_push_for_new_incident_goes_to_those_who_see_it(setup, tmp_path: Path) -> None:
    from tests.test_push import Device, FakePost

    push = PushService(SimpleNamespace(sources=[]), setup.auth, key_file=tmp_path / "k", post=FakePost())
    for username in ("b-zuschauer", "a-admin", "kreis"):
        data = Device(f"https://fcm.googleapis.com/fcm/send/{username}").json()
        push.subscribe(session(setup.auth, username), endpoint=data["endpoint"],
                       p256dh=data["keys"]["p256dh"], auth=data["keys"]["auth"])
    incident = create(setup)
    notice = Notice(event="incident_started", subject="Einsatz", body="x", incident_id=incident["id"])

    owners = {setup.auth.ready().user_by_id(item["user_id"])["username"] for item in push.recipients(notice)}
    assert owners == {"b-zuschauer", "kreis"}


# ----------------------------------------------------------------------
# Schnittstelle
# ----------------------------------------------------------------------


@pytest.fixture
def api(auth, tmp_path: Path, monkeypatch):  # noqa: F811
    from fastapi.testclient import TestClient

    from open_bos_stream.api import incidents as incidents_api
    from open_bos_stream.core import container
    from open_bos_stream.core.event_log import ServerEventLog
    from open_bos_stream.main import app

    real = container.auth_service
    for name in ("org", "_ready", "users_file", "secret_file", "revoked_file", "_secret_cache", "_incidents"):
        monkeypatch.setattr(real, name, getattr(auth, name))
    store = GuestLinkStore(tmp_path / "guest_links.json")
    monkeypatch.setattr(real, "guest_links", store)
    monkeypatch.setattr(incidents_api, "guest_link_store", store)
    from open_bos_stream.api import guest as guest_api

    monkeypatch.setattr(guest_api, "guest_link_store", store)
    monkeypatch.setattr(guest_api, "server_event_log", ServerEventLog(None))
    monkeypatch.setattr(incidents_api, "server_event_log", ServerEventLog(None))
    monkeypatch.setattr(incidents_api, "capture_weather", lambda *args, **kwargs: False)
    monkeypatch.setattr(incidents_api.push_service, "enqueue", lambda notice: True)
    ids = build(real)
    drone = source("b1", ids["b"])
    monkeypatch.setattr(incidents_api.config, "sources", [drone])
    client = TestClient(app)

    def login(username: str) -> None:
        client.cookies.clear()
        client.cookies.set(real.COOKIE_NAME, real.create_token(real.authenticate(username, PASSWORD)))

    client.login = login
    client.ids = ids
    return client


def test_incident_api_flow(api) -> None:
    api.login("b-zuschauer")
    assert api.get("/api/incidents").json()["lead_options"] == []
    assert api.post("/api/incidents", json={"lead_organization_id": api.ids["b"]}).status_code == 403

    api.login("b-team")
    created = api.post("/api/incidents", json={
        "lead_organization_id": api.ids["b"],
        "alarm_at": "2026-11-26T14:32",
        "keyword": "TH Person vermisst",
        "address": "Waldweg 1, Hagen",
        "source_ids": ["b1"],
    })
    assert created.status_code == 200
    incident_id = created.json()["incident"]["id"]

    detail = api.get(f"/api/incidents/{incident_id}").json()
    assert detail["can"] == {"edit": True, "administer": False}
    assert [item["source_id"] for item in detail["sources"]] == ["b1"]
    assert detail["available_sources"] == []

    link = api.post(f"/api/incidents/{incident_id}/guest-links", json={"label": "Polizei", "hours": 4})
    assert link.status_code == 200 and "/g/" in link.json()["url"]

    report = api.get(f"/api/incidents/{incident_id}/report")
    assert report.status_code == 200
    assert "2026-11-26-1432" in report.text and "Waldweg 1, Hagen" in report.text

    ended = api.post(f"/api/incidents/{incident_id}/status", json={"status": "ended"})
    assert ended.json()["incident"]["status"] == "ended"
    assert ended.json()["guest_links"][0]["active"] is False

    assert api.delete(f"/api/incidents/{incident_id}").status_code == 403
    api.login("a-admin")
    assert api.get(f"/api/incidents/{incident_id}").status_code == 404
    api.login("kreis")
    assert api.delete(f"/api/incidents/{incident_id}").status_code == 200


def test_exercise_is_marked_everywhere(setup) -> None:
    incident = create(setup, exercise=True)
    assert incident["exercise"] is True
    assert setup.incidents.log(incident["id"])[0]["text"].startswith("Übung angelegt")

    team = session(setup.auth, "b-team")
    real = setup.incidents.update(team, incident["id"], exercise=False)
    assert real["exercise"] is False
    assert setup.incidents.log(incident["id"])[-1]["text"] == "Als Realeinsatz gekennzeichnet"


def test_exercise_report_and_push_subject(api, monkeypatch) -> None:
    from open_bos_stream.api import incidents as incidents_api

    sent = []
    monkeypatch.setattr(incidents_api.push_service, "enqueue", sent.append)
    api.login("b-team")
    created = api.post("/api/incidents", json={
        "lead_organization_id": api.ids["b"], "keyword": "Flächensuche", "exercise": True,
    }).json()["incident"]
    assert created["exercise"] is True
    assert sent[0].subject == "Übung: Flächensuche"
    report = api.get(f"/api/incidents/{created['id']}/report").text
    assert "Übungsbericht" in report and "ÜBUNG – kein Realeinsatz" in report
    assert api.get(f"/api/incidents/{created['id']}/map").json()["exercise"] is True


# ----------------------------------------------------------------------
# Sicherheits-Update 0.25.1
# ----------------------------------------------------------------------


def test_foreign_incident_drone_is_visible_without_secrets(setup) -> None:
    from open_bos_stream.api.config import fetches_internal_address, visible_config_sources
    from open_bos_stream.core.models import SourceConfig

    own = SourceConfig(id="a1", name="Drohne A", type="rtmp", organization_id=setup.ids["a"])
    foreign = SourceConfig(
        id="b1", name="Drohne B", type="rtmp", organization_id=setup.ids["b"],
        publish_password="geheim-passwort",
    )
    camera = SourceConfig(
        id="kamera", name="Kamera", type="rtsp", organization_id=setup.ids["b"],
        url="rtsp://nutzer:pass@203.0.113.5/live",
    )
    team = session(setup.auth, "b-team")
    incident = create(setup)
    setup.incidents.add_source(team, incident["id"], foreign)
    setup.incidents.add_source(team, incident["id"], camera)
    setup.incidents.add_organization(team, incident["id"], setup.ids["a"])

    visible = {item.id: item for item in visible_config_sources(session(setup.auth, "a-admin"), [own, foreign, camera])}
    assert visible["a1"].publish_token == own.publish_token
    assert visible["b1"].publish_token is None and visible["b1"].model_extra["publish_password"] is None
    assert visible["kamera"].url == "rtsp://***@203.0.113.5/live"
    # Admins der eigenen Wehr sehen weiterhin alles.
    assert visible_config_sources(session(setup.auth, "kreis"), [foreign])[0].publish_token == foreign.publish_token

    internal = SourceConfig(id="x", name="X", type="http", url="http://127.0.0.1:9997/v3/config/global/get")
    assert fetches_internal_address(internal)
    assert fetches_internal_address(SourceConfig(id="y", name="Y", type="rtsp", url="rtsp://192.168.1.10/live"))
    assert not fetches_internal_address(SourceConfig(id="z", name="Z", type="rtsp", url="rtsp://9.9.9.9/live"))


def test_involved_wehr_cannot_take_over_the_lead(setup) -> None:
    incident = create(setup)
    team = session(setup.auth, "b-team")
    setup.incidents.add_organization(team, incident["id"], setup.ids["a"])
    with pytest.raises(IncidentAccessError):
        setup.incidents.update(session(setup.auth, "a-admin"), incident["id"], lead_organization_id=setup.ids["a"])
    # Auch das Drohnenteam der führenden Wehr übergibt nicht.
    with pytest.raises(IncidentAccessError):
        setup.incidents.update(team, incident["id"], lead_organization_id=setup.ids["a"])
    moved = setup.incidents.update(session(setup.auth, "kreis"), incident["id"], lead_organization_id=setup.ids["a"])
    assert moved["lead_organization_id"] == setup.ids["a"]


def test_cached_permissions_follow_changes_immediately(setup) -> None:
    from open_bos_stream.core.models import SourceConfig

    foreign = SourceConfig(id="b1", name="Drohne B", type="rtmp", organization_id=setup.ids["b"])
    team = session(setup.auth, "b-team")
    incident = create(setup)
    setup.incidents.add_source(team, incident["id"], foreign)
    assert session(setup.auth, "a-admin")["incident_source_ids"] == []
    setup.incidents.add_organization(team, incident["id"], setup.ids["a"])
    # Ohne Wartezeit: Der Änderungszähler macht den Cache ungültig.
    assert session(setup.auth, "a-admin")["incident_source_ids"] == ["b1"]
    setup.incidents.set_status(team, incident["id"], "ended")
    assert session(setup.auth, "a-admin")["incident_source_ids"] == []


def test_weather_capture_keeps_earlier_values(api) -> None:
    from open_bos_stream.api import incidents as incidents_api

    api.login("b-team")
    incident_id = api.post("/api/incidents", json={
        "lead_organization_id": api.ids["b"],
        "keyword": "F Wald",
    }).json()["incident"]["id"]
    service = incidents_api._service()

    for wind, time in ((3.5, "2026-11-26T14:35"), (9.0, "2026-11-26T16:10")):
        service.set_weather(incident_id, {
            "captured_at": time,
            "current": {"wind_speed_ms": wind},
            "assessment": {"summary": "Flugbetrieb möglich"},
        }, "System")

    detail = api.get(f"/api/incidents/{incident_id}").json()
    assert detail["incident"]["weather"]["current"]["wind_speed_ms"] == 3.5
    assert [entry["current"]["wind_speed_ms"] for entry in detail["incident"]["weather_history"]] == [3.5, 9.0]
    texts = [entry["text"] for entry in detail["log"] if entry["kind"] == "weather"]
    assert any("Wind 3,5 m/s" in text for text in texts)
    assert any("Wind 9,0 m/s" in text for text in texts)

    report = api.get(f"/api/incidents/{incident_id}/report").text
    assert "Erste Erfassung" in report and "Erneute Erfassung" in report
    assert "3.5 m/s" in report and "9.0 m/s" in report


def test_weather_stored_before_history_is_kept() -> None:
    from open_bos_stream.incidents.service import _weather_history

    assert _weather_history('{"captured_at": "x"}') == [{"captured_at": "x"}]
    assert _weather_history(None) == []
    assert _weather_history("kaputt") == []


def test_weather_follows_the_incident_of_the_own_unit(api, monkeypatch) -> None:
    from open_bos_stream.api import weather as weather_api

    monkeypatch.setattr(weather_api.weather_service, "report", lambda *args: {})
    api.login("b-team")
    created = api.post("/api/incidents", json={
        "lead_organization_id": api.ids["b"],
        "address": "Waldweg 1",
        "latitude": 53.5,
        "longitude": 9.6,
    })
    key = f"incident:{created.json()['incident']['id']}"

    report = api.get("/api/weather").json()
    assert report["automatic_place"] == key
    assert report["location"]["latitude"] == 53.5
    assert api.get("/api/weather?place=default").json()["location"]["key"] == "default"
    # Unbekannte Orte (z. B. beendeter Einsatz) führen zur automatischen Wahl.
    assert api.get("/api/weather?place=incident:999").json()["location"]["key"] == key
