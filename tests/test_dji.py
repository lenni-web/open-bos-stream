from __future__ import annotations

import json
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from open_bos_stream.db.schema import drone_records
from open_bos_stream.dji.config import load_config
from open_bos_stream.dji.service import DroneService, utc_now
from open_bos_stream.dji.telemetry import extract, parse_topic
from open_bos_stream.incidents.service import IncidentAccessError, IncidentError
from tests.test_incidents import api, create, setup  # noqa: F401
from tests.test_organizations import auth, session  # noqa: F401


RC = "RC0001"
DRONE = "UAV0001"


class Clock:
    def __init__(self) -> None:
        self.now = utc_now()

    def __call__(self):
        return self.now

    def tick(self, **delta) -> None:
        self.now += timedelta(**delta)


def topology(service, children=((DRONE, 77, 1),)):
    return service.handle(f"sys/product/{RC}/status", json.dumps({
        "tid": "t1", "bid": "b1", "method": "update_topo",
        "data": {"type": 144, "sub_type": 0, "sub_devices": [
            {"sn": sn, "type": kind, "sub_type": sub} for sn, kind, sub in children
        ]},
    }))


def osd(service, serial=DRONE, **data):
    values = {"latitude": 53.5, "longitude": 9.5, "elevation": 40.0, "mode_code": 3,
              "battery": {"capacity_percent": 80}, "unbekanntes_feld": {"bleibt": True}}
    values.update(data)
    return service.handle(f"thing/product/{serial}/osd", json.dumps({"gateway": RC, "data": values}))


def records(service, incident_id) -> int:
    with service.org.db.engine.connect() as connection:
        return connection.execute(
            select(func.count()).select_from(drone_records)
            .where(drone_records.c.incident_id == incident_id)
        ).scalar_one()


def claim(setup, service, organization="b") -> None:  # noqa: F811
    service.update_device(session(setup.auth, "kreis"), DRONE, name="Florian 1",
                          organization_id=setup.ids[organization])


def test_topic_and_values() -> None:
    assert parse_topic("thing/product/ABC123/osd") == ("ABC123", "osd")
    assert parse_topic("thing/product/../osd") is None
    assert parse_topic("andere/product/ABC/osd") is None
    assert "latitude" not in extract({"latitude": 0, "longitude": 0})
    assert extract({"capacity_percent": 55}) == {"battery": 55}
    assert extract({"latitude": "53", "elevation": True}) == {}


def test_topology_is_answered_and_registers_devices(setup) -> None:  # noqa: F811
    service = DroneService(setup.incidents)
    replies = topology(service)

    assert replies[0][0] == f"sys/product/{RC}/status_reply"
    answer = json.loads(replies[0][1])
    assert answer["tid"] == "t1" and answer["data"] == {"result": 0}
    assert service.device(DRONE)["model"] == "DJI Mavic 3T"
    assert service.device(DRONE)["gateway_serial"] == RC
    assert service.device(RC)["kind"] == "controller"
    # Neue Geräte sehen nur Admins, bis eine Wehr sie übernimmt.
    assert service.devices(session(setup.auth, "b-zuschauer")) == []
    assert len(service.devices(session(setup.auth, "kreis"))) == 2


def test_broken_messages_are_ignored(setup) -> None:  # noqa: F811
    service = DroneService(setup.incidents)
    for payload in (b"\xff", "kein json", "[1]", "x" * 300_000):
        assert service.handle(f"thing/product/{DRONE}/osd", payload) == []
    assert service.device(DRONE) is None


def test_all_data_is_recorded_with_the_only_running_incident(setup) -> None:  # noqa: F811
    clock = Clock()
    service = DroneService(setup.incidents, clock)
    topology(service)
    claim(setup, service)
    incident = create(setup, alarm_at=None)

    osd(service)
    osd(service, serial=RC, capacity_percent=60, battery=None)

    assert [item["serial"] for item in service.assignments(incident["id"])] == [DRONE]
    lines = [json.loads(line) for line in service.export_jsonl(incident["id"])]
    assert [line["serial"] for line in lines][-2:] == [DRONE, RC]
    assert lines[-2]["payload"]["data"]["unbekanntes_feld"] == {"bleibt": True}
    csv = "".join(service.export_csv(incident["id"]))
    assert "Florian 1" in csv and "Manueller Flug" in csv
    summary = {item["serial"]: item for item in service.summary(incident["id"])}
    assert summary[DRONE]["max_elevation"] == 40.0 and summary[DRONE]["min_battery"] == 80
    assert any("aufgezeichnet" in entry["text"] for entry in setup.incidents.log(incident["id"]))


def test_assignment_backfills_since_alarm_and_stops_with_incident(setup) -> None:  # noqa: F811
    clock = Clock()
    service = DroneService(setup.incidents, clock)
    topology(service)
    claim(setup, service)
    clock.tick(hours=-2)
    osd(service)  # Übungsflug lange vor dem Alarm
    clock.tick(hours=2)
    first = create(setup, alarm_at=None)
    second = create(setup, alarm_at=None, keyword="Zweiter Einsatz")
    clock.tick(seconds=5)
    osd(service)  # zwei laufende Einsätze: keine automatische Zuordnung
    assert records(service, first["id"]) == 0

    team = session(setup.auth, "b-team")
    service.assign(team, first["id"], DRONE)
    assert records(service, first["id"]) >= 1
    with pytest.raises(IncidentError):
        service.assign(team, second["id"], DRONE)
    count = records(service, first["id"])
    csv_rows = "".join(service.export_csv(first["id"])).strip().splitlines()
    assert len(csv_rows) == 2  # Kopf und nur die Meldung seit Alarm

    setup.incidents.set_status(team, first["id"], "ended")
    assert not service.assignments(first["id"])[0]["active"]
    osd(service)
    assert records(service, first["id"]) == count


def test_released_drone_is_not_assigned_again(setup) -> None:  # noqa: F811
    service = DroneService(setup.incidents)
    topology(service)
    claim(setup, service)
    incident = create(setup, alarm_at=None)
    osd(service)
    service.release(session(setup.auth, "b-team"), incident["id"], DRONE)
    count = records(service, incident["id"])
    osd(service)
    assert records(service, incident["id"]) == count
    assert not service.assignments(incident["id"])[0]["active"]


def test_unassigned_data_expires_but_incident_data_stays(setup) -> None:  # noqa: F811
    clock = Clock()
    service = DroneService(setup.incidents, clock)
    topology(service)
    claim(setup, service)
    incident = create(setup, alarm_at=None)
    clock.tick(seconds=1)
    osd(service)
    kept = records(service, incident["id"])
    service.release(session(setup.auth, "b-team"), incident["id"], DRONE)
    osd(service)
    clock.tick(hours=25)
    service.purge()
    assert records(service, None) == 0
    assert records(service, incident["id"]) == kept


def test_blocked_devices_and_rights(setup) -> None:  # noqa: F811
    service = DroneService(setup.incidents)
    topology(service)
    claim(setup, service)
    incident = create(setup, alarm_at=None)
    with pytest.raises(LookupError):
        service.assign(session(setup.auth, "a-admin"), incident["id"], DRONE)
    with pytest.raises(IncidentAccessError):
        service.update_device(session(setup.auth, "b-team"), DRONE, name="x")
    service.update_device(session(setup.auth, "kreis"), DRONE, blocked=True)
    before = records(service, None)
    osd(service)
    assert records(service, None) == before and records(service, incident["id"]) == 0


def test_live_positions_and_shared_locations_expire(setup) -> None:  # noqa: F811
    clock = Clock()
    service = DroneService(setup.incidents, clock)
    topology(service)
    claim(setup, service)
    incident = create(setup, alarm_at=None)
    osd(service)
    osd(service, serial=RC, latitude=53.51)
    team = session(setup.auth, "b-team")
    service.share_location(team, incident["id"], 53.4, 9.4, 12.3)

    state = service.positions(incident)
    assert state["drones"][0]["state"]["online"]
    assert state["drones"][0]["track"] == [[9.5, 53.5]]
    assert state["drones"][0]["controller"]["latitude"] == 53.51
    assert state["persons"][0]["accuracy"] == 12
    assert service.positions(incident, after=state["last"])["drones"][0]["track"] == []

    clock.tick(minutes=3)
    state = service.positions(incident)
    assert state["persons"] == [] and not state["drones"][0]["state"]["online"]


def test_config_is_disabled_without_file(tmp_path) -> None:
    assert not load_config(tmp_path / "fehlt.yaml").enabled
    path = tmp_path / "dji.yaml"
    path.write_text("app_id: 1\napp_key: k\nlicense: l\npilot_username: pilot\n"
                    "pilot_password: p\npublic_port: '8883'\n", encoding="utf-8")
    config = load_config(path)
    assert config.licensed and not config.enabled
    assert config.public_address("beispiel.de") == "ssl://beispiel.de:8883"
    assert len(config.workspace()) == 36


def test_api_pilot_page_config_and_incident_data(api, monkeypatch, tmp_path) -> None:  # noqa: F811
    from open_bos_stream.api import dji as dji_api
    from open_bos_stream.dji.config import DjiConfig

    monkeypatch.setattr(dji_api, "load_config", lambda: DjiConfig(
        app_id="1", app_key="schluessel", license="lizenz", pilot_username="pilot", pilot_password="geheim",
    ))
    api.cookies.clear()
    page = api.get("/dji")
    assert page.status_code == 200 and "geheim" not in page.text and "schluessel" not in page.text
    assert api.get("/api/dji/pilot-config").status_code == 401
    api.login("b-zuschauer")
    assert api.get("/api/dji/pilot-config").status_code == 403
    api.login("b-team")
    config = api.get("/api/dji/pilot-config")
    assert config.json()["mqtt"]["password"] == "geheim"
    assert config.headers["cache-control"] == "no-store"

    incident_id = api.post("/api/incidents", json={
        "lead_organization_id": api.ids["b"], "keyword": "Suche",
    }).json()["incident"]["id"]
    service = dji_api.drone_service()
    topology(service)
    service.update_device(session_of_kreis(service), DRONE, organization_id=api.ids["b"])
    osd(service)

    assert api.get(f"/api/incidents/{incident_id}/drones").json()["drones"][0]["serial"] == DRONE
    assert api.get(f"/api/incidents/{incident_id}/positions").json()["drones"][0]["track"]
    assert api.put(f"/api/incidents/{incident_id}/location",
                   json={"latitude": 53.4, "longitude": 9.4}).status_code == 200
    assert DRONE in api.get(f"/api/incidents/{incident_id}/telemetry.csv").text
    assert "Aufgezeichnete Drohnendaten" in api.get(f"/api/incidents/{incident_id}/report").text
    assert api.get("/api/dji/live").json()["drones"][0]["serial"] == DRONE
    # Einsatz-Gastlink: Drohnen ja, Personen und Pilotenstandort nein.
    link = api.post(f"/api/incidents/{incident_id}/guest-links", json={"label": "ELW", "hours": 1}).json()
    api.cookies.clear()
    api.get(link["url"])
    guest = api.get("/guest/incident-positions").json()
    assert guest["drones"][0]["serial"] == DRONE
    assert guest["persons"] == [] and guest["drones"][0]["controller"] is None
    assert api.get(f"/api/incidents/{incident_id}/telemetry.jsonl").status_code == 403

    api.login("a-admin")
    assert api.get(f"/api/incidents/{incident_id}/positions").status_code == 404
    assert api.get(f"/api/incidents/{incident_id}/telemetry.jsonl").status_code == 404
    assert api.get("/api/dji/live").json()["drones"] == []


def test_viewers_see_only_their_own_drones_without_secrets(api, monkeypatch) -> None:  # noqa: F811
    from open_bos_stream.api import dji as dji_api
    from tests.test_organizations import source

    monkeypatch.setattr(dji_api.config, "sources",
                        [source("b1", api.ids["b"]), source("a1", api.ids["a"]), source("frei", None)])
    api.login("b-zuschauer")
    response = api.get("/api/drones/sources")
    sources = response.json()["sources"]
    assert len(sources) == 1 and set(sources[0]) == {"name", "drone_type", "enabled", "organization_name"}
    assert "token" not in response.text and "rtmp://" not in response.text

    service = dji_api.drone_service()
    topology(service)
    service.update_device(session_of_kreis(service), DRONE, organization_id=api.ids["b"])
    devices = api.get("/api/dji/devices").json()["devices"]
    assert [(item["serial"], item["can_manage"]) for item in devices] == [(DRONE, False)]
    assert api.patch(f"/api/dji/devices/{DRONE}", json={"name": "x"}).status_code == 403
    page = api.get("/").text
    assert 'id="drone-source-list"' in page and 'id="source-settings"' not in page

    api.login("a-admin")
    assert DRONE not in [item["serial"] for item in api.get("/api/dji/devices").json()["devices"]]


def session_of_kreis(service) -> dict:
    return {"username": "kreis", "role": "admin", "server_admin": True, "org_view": [], "org_admin": []}
