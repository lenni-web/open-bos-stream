from __future__ import annotations

from datetime import timedelta

from sqlalchemy import update

from open_bos_stream.db.schema import incident_participants
from open_bos_stream.incidents.drone_history import drone_history
from open_bos_stream.incidents.service import iso, local_now
from tests.test_incidents import api, create, setup  # noqa: F401
from tests.test_organizations import auth, session, source  # noqa: F401


def history(setup, username: str = "b-team") -> dict:  # noqa: F811
    return drone_history(
        setup.incidents, session(setup.auth, username), source_ids=["b1", "leer"],
    )["sources"]


def person(setup, incident, name, role="fernpilot", **extra) -> dict:  # noqa: F811
    return setup.incidents.add_participant(
        session(setup.auth, "b-team"), incident["id"], name=name, role=role, **extra,
    )


def fly(setup, **extra) -> dict:  # noqa: F811
    incident = create(setup, alarm_at=None, **extra)
    setup.incidents.add_source(session(setup.auth, "b-team"), incident["id"], source("b1", setup.ids["b"]))
    return incident


def test_every_incident_counts_once_including_exercises(setup) -> None:  # noqa: F811
    team = session(setup.auth, "b-team")
    first = fly(setup)
    # Zweimal im selben Einsatz bleibt ein Einsatz.
    setup.incidents.remove_source(team, first["id"], "b1")
    setup.incidents.add_source(team, first["id"], source("b1", setup.ids["b"]))
    fly(setup, exercise=True)

    result = history(setup)
    assert result["b1"]["count"] == 2 and result["b1"]["hidden"] == 0
    assert [item["exercise"] for item in result["b1"]["incidents"]].count(True) == 1
    assert result["leer"] == {"count": 0, "hidden": 0, "incidents": []}


def test_persons_are_those_whose_time_overlaps_the_drone(setup) -> None:  # noqa: F811
    incident = fly(setup)
    team = session(setup.auth, "b-team")
    hour = timedelta(hours=1)
    person(setup, incident, "Anna Pilot")
    person(setup, incident, "Anna Pilot", role="dokumentation")
    person(setup, incident, "Vorher Weg", from_at=iso(local_now() - 2 * hour), until_at=iso(local_now() - hour))
    setup.incidents.set_status(team, incident["id"], "ended", ended_at=iso(local_now() + hour))
    person(setup, incident, "Zu Spät", from_at=iso(local_now() + 2 * hour), until_at=iso(local_now() + 3 * hour))

    persons = history(setup)["b1"]["incidents"][0]["persons"]
    assert [item["name"] for item in persons] == ["Anna Pilot"]
    assert persons[0]["roles"] == ["Fernpilot", "Dokumentation"]


def test_persons_added_after_the_incident_are_kept(setup) -> None:  # noqa: F811
    incident = fly(setup)
    team = session(setup.auth, "b-team")
    setup.incidents.set_status(team, incident["id"], "ended")
    entry = person(setup, incident, "Nach Getragen")
    with setup.incidents.org.db.engine.begin() as connection:
        connection.execute(
            update(incident_participants)
            .where(incident_participants.c.id == entry["id"])
            .values(from_at=iso(local_now() + timedelta(days=1)))
        )

    assert [item["name"] for item in history(setup)["b1"]["incidents"][0]["persons"]] == ["Nach Getragen"]


def test_names_are_only_visible_with_access_to_the_incident(setup) -> None:  # noqa: F811
    incident = fly(setup)
    person(setup, incident, "Anna Pilot")

    foreign = history(setup, "a-admin")["b1"]
    assert foreign == {"count": 1, "hidden": 1, "incidents": []}
    assert history(setup, "b-zuschauer")["b1"]["incidents"][0]["persons"]


def test_history_api_covers_sources_and_dji_drones(api, monkeypatch) -> None:  # noqa: F811
    from open_bos_stream.api import dji as dji_api
    from tests.test_dji import DRONE, osd, session_of_kreis, topology

    monkeypatch.setattr(dji_api.config, "sources", [source("b1", api.ids["b"])])
    service = dji_api.drone_service()
    topology(service)
    service.update_device(session_of_kreis(service), DRONE, organization_id=api.ids["b"])
    api.login("b-team")
    incident_id = api.post("/api/incidents", json={"lead_organization_id": api.ids["b"]}).json()["incident"]["id"]
    osd(service)
    api.post(f"/api/incidents/{incident_id}/participants", json={"name": "Anna Pilot", "role": "fernpilot"})

    result = api.get("/api/drones/history").json()
    assert result["devices"][DRONE]["count"] == 1
    assert result["devices"][DRONE]["incidents"][0]["persons"][0]["name"] == "Anna Pilot"
    assert result["sources"]["b1"]["count"] == 0

    # Fremde Wehr: weder die Drohnen noch die Namen.
    api.login("a-admin")
    response = api.get("/api/drones/history")
    assert response.json() == {"sources": {}, "devices": {}}
    assert "Anna" not in response.text
