from __future__ import annotations

from pathlib import Path

import pytest

from open_bos_stream.auth.guest_links import GuestLinkStore
from open_bos_stream.incidents.map import IncidentMap, clean_polygon, column_label
from open_bos_stream.incidents.service import IncidentAccessError, IncidentError
from tests.test_incidents import api, create, setup  # noqa: F401
from tests.test_organizations import auth, session  # noqa: F401


SQUARE = {"type": "Polygon", "coordinates": [[[9.50, 53.50], [9.51, 53.50], [9.51, 53.51], [9.50, 53.51]]]}


def test_grid_is_named_from_top_left_and_bumps_revision(setup) -> None:  # noqa: F811
    incident = create(setup)
    incident_map = IncidentMap(setup.incidents)
    team = session(setup.auth, "b-team")
    assert incident_map.revision(incident["id"]) == 0

    items = incident_map.add_grid(team, incident["id"], west=9.5, south=53.5, east=9.53, north=53.52, rows=2, columns=3)

    assert [item["name"] for item in items] == ["A1", "A2", "B1", "B2", "C1", "C2"]
    a1 = next(item for item in items if item["name"] == "A1")
    ring = a1["geometry"]["coordinates"][0]
    assert ring[0] == [9.5, 53.52]  # oben links
    assert incident_map.revision(incident["id"]) == 1
    assert any("Raster 2 × 3" in entry["text"] for entry in setup.incidents.log(incident["id"]))

    with pytest.raises(IncidentError, match="Präfix"):
        incident_map.add_grid(team, incident["id"], west=9.5, south=53.5, east=9.53, north=53.52, rows=1, columns=1)
    second = incident_map.add_grid(team, incident["id"], west=9.6, south=53.5, east=9.61, north=53.51,
                                   rows=1, columns=2, prefix="N-")
    assert {"N-A1", "N-B1"} <= {item["name"] for item in second}


def test_status_changes_are_logged_and_visible_to_involved_wehren(setup) -> None:  # noqa: F811
    incident = create(setup)
    incident_map = IncidentMap(setup.incidents)
    team = session(setup.auth, "b-team")
    item = incident_map.add_item(team, incident["id"], name="Waldstück", geometry=SQUARE)
    assert item["geometry"]["coordinates"][0][0] == item["geometry"]["coordinates"][0][-1]

    setup.incidents.add_organization(team, incident["id"], setup.ids["a"])
    a_admin = session(setup.auth, "a-admin")
    updated = incident_map.update_item(a_admin, incident["id"], item["id"], status="done", assignee="Drohne 2")
    assert updated["status_label"] == "abgesucht" and updated["updated_by"] == "a-admin"
    assert any("Waldstück: abgesucht, zuständig: Drohne 2" in entry["text"] for entry in setup.incidents.log(incident["id"]))

    with pytest.raises(IncidentAccessError):
        incident_map.add_item(session(setup.auth, "b-zuschauer"), incident["id"], name="X", geometry=SQUARE)


def test_polygon_validation() -> None:
    with pytest.raises(IncidentError):
        clean_polygon({"type": "Point", "coordinates": [9, 53]})
    with pytest.raises(IncidentError):
        clean_polygon({"type": "Polygon", "coordinates": [[[9, 53], [9.1, 53]]]})
    with pytest.raises(IncidentError, match="zu groß"):
        clean_polygon({"type": "Polygon", "coordinates": [[[9, 53], [10, 53], [10, 54]]]})
    with pytest.raises(IncidentError):
        clean_polygon({"type": "Polygon", "coordinates": [[[9, 53], [200, 53], [9, 54]]]})
    assert column_label(0) == "A" and column_label(25) == "Z" and column_label(26) == "AA"


def test_map_api_sync_and_guest_view(api, tmp_path: Path) -> None:  # noqa: F811
    api.login("b-team")
    incident_id = api.post("/api/incidents", json={
        "lead_organization_id": api.ids["b"], "keyword": "Flächensuche",
    }).json()["incident"]["id"]

    state = api.get(f"/api/incidents/{incident_id}/map").json()
    assert state["changed"] and state["items"] == [] and state["can_edit"]
    revision = state["revision"]
    assert api.get(f"/api/incidents/{incident_id}/map?since={revision}").json()["changed"] is False

    created = api.post(f"/api/incidents/{incident_id}/map/grid", json={
        "west": 9.5, "south": 53.5, "east": 9.52, "north": 53.52, "rows": 2, "columns": 2,
    })
    assert created.status_code == 200 and len(created.json()["items"]) == 4
    moved = api.put(f"/api/incidents/{incident_id}/map/position", json={"latitude": 53.51, "longitude": 9.51})
    assert moved.json()["position"] == {"latitude": 53.51, "longitude": 9.51}

    # Andere Zuschauer derselben Wehr sehen die Änderung beim nächsten Abgleich.
    api.login("b-zuschauer")
    seen = api.get(f"/api/incidents/{incident_id}/map?since={revision}").json()
    assert seen["changed"] and len(seen["items"]) == 4 and seen["can_edit"] is False
    item_id = seen["items"][0]["id"]
    assert api.patch(f"/api/incidents/{incident_id}/map/items/{item_id}", json={"status": "done"}).status_code == 403

    # Einsatz-Gastlink: Karte nur lesen.
    api.login("b-team")
    url = api.post(f"/api/incidents/{incident_id}/guest-links", json={"label": "Polizei", "hours": 2}).json()["url"]
    api.cookies.clear()
    opened = api.get(url[url.index("/g/"):], follow_redirects=False)
    assert opened.status_code == 303
    guest_map = api.get("/guest/incident-map").json()
    assert len(guest_map["items"]) == 4 and guest_map["can_edit"] is False
    assert api.post(f"/api/incidents/{incident_id}/map/items", json={"name": "X", "geometry": {}}).status_code == 403


def test_own_areas_are_drawn_above_other_layers_with_a_casing() -> None:
    static = Path(__file__).resolve().parents[1] / "src" / "open_bos_stream" / "static" / "js"
    script = (static / "map-incident.js").read_text(encoding="utf-8")
    assert script.index('id: "incident-items-casing"') < script.index('id: "incident-items-line"')
    # Die Einsatzkarte wird nach Geozonen und Radar eingebunden.
    start = (static / "map.js").read_text(encoding="utf-8")
    assert start.index("addDipulLayers(") < start.index("initIncidentMap(map)")
    assert start.index("addWeatherLayers(") < start.index("initIncidentMap(map)")


def test_search_estimate_is_loaded_before_the_incident_map() -> None:
    package = Path(__file__).resolve().parents[1] / "src" / "open_bos_stream"
    for page in ("index.html", "guest.html"):
        template = (package / "templates" / page).read_text(encoding="utf-8")
        assert template.index("search-estimate.js") < template.index("map-incident.js")


def test_assignee_can_be_picked_from_drones_or_typed() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "src" / "open_bos_stream" / "static" / "js" / "map-incident.js"
    ).read_text(encoding="utf-8")

    assert "/api/dji/devices" in script
    assert "/api/drones/sources" in script
    assert 'id="incident-assignee-choice"' in script
    assert "Drohne / Trupp manuell eingeben" in script
    # Das Formular speichert weiterhin das Feld „assignee“.
    assert 'name="assignee"' in script


def test_unchanged_map_state_still_reports_the_status(monkeypatch) -> None:
    from open_bos_stream.api import incidents as api_incidents

    class Map:
        def revision(self, incident_id):
            return 3

    monkeypatch.setattr(api_incidents, "_map", lambda: Map())
    state = api_incidents.map_state({"id": 7, "status": "ended"}, since=3)

    assert state["changed"] is False
    assert state["status"] == "ended"


@pytest.mark.parametrize("status", ["ended", "closed"])
def test_map_is_read_only_after_the_incident(setup, status) -> None:  # noqa: F811
    incident = create(setup)
    incident_map = IncidentMap(setup.incidents)
    team = session(setup.auth, "b-team")
    item = incident_map.add_item(team, incident["id"], name="A1", geometry=SQUARE)
    setup.incidents.set_status({"username": "root", "platform_admin": True}, incident["id"], status)
    root = {"username": "root", "platform_admin": True}

    for user in (team, root):
        with pytest.raises((IncidentError, IncidentAccessError)):
            incident_map.add_item(user, incident["id"], name="A2", geometry=SQUARE)
        with pytest.raises((IncidentError, IncidentAccessError)):
            incident_map.add_grid(
                user, incident["id"], west=9.5, south=53.5, east=9.51, north=53.51, rows=1, columns=1,
            )
        with pytest.raises((IncidentError, IncidentAccessError)):
            incident_map.update_item(user, incident["id"], item["id"], name="B9")
        with pytest.raises((IncidentError, IncidentAccessError)):
            incident_map.delete_item(user, incident["id"], item["id"])
    assert [entry["name"] for entry in incident_map.items(incident["id"])] == ["A1"]


def test_follow_ups_after_the_end_are_logged_for_the_report(setup) -> None:  # noqa: F811
    incident = create(setup)
    incident_map = IncidentMap(setup.incidents)
    team = session(setup.auth, "b-team")
    item = incident_map.add_item(team, incident["id"], name="A1", geometry=SQUARE)
    root = {"username": "root", "platform_admin": True}
    setup.incidents.set_status(root, incident["id"], "ended")

    changed = incident_map.update_item(
        team, incident["id"], item["id"], status="done", note="Nichts gefunden",
    )
    # Unverändert speichern erzeugt keinen zweiten Nachtrag.
    incident_map.update_item(team, incident["id"], item["id"], status="done", note="Nichts gefunden")

    assert changed["status"] == "done" and changed["note"] == "Nichts gefunden"
    entries = [e for e in setup.incidents.log(incident["id"]) if e["kind"] == "followup"]
    assert [e["text"] for e in entries] == [
        "Nachtrag Quadrant A1: Status offen → abgesucht, Notiz: „Nichts gefunden“"
    ]

    setup.incidents.set_status(root, incident["id"], "closed")
    with pytest.raises(IncidentError):
        incident_map.update_item(root, incident["id"], item["id"], status="open")


def test_report_lists_follow_ups() -> None:
    report = (
        Path(__file__).resolve().parents[1]
        / "src" / "open_bos_stream" / "templates" / "incident_report.html"
    ).read_text(encoding="utf-8")
    assert 'selectattr("kind", "equalto", "followup")' in report
    assert "Nachträge nach Einsatzende" in report
