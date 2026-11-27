from __future__ import annotations

from pathlib import Path

import pytest

from open_bos_stream.checklists.documents import DocumentStore
from open_bos_stream.checklists.service import (
    ChecklistAccessError,
    ChecklistError,
    ChecklistService,
)
from tests.test_incidents import api, create, setup  # noqa: F401
from tests.test_organizations import auth, session  # noqa: F401


ITEMS = [
    {"section": "Vor dem Start", "text": "Akkus geladen", "required": True},
    {"section": "Vor dem Start", "text": "Luftraum geprüft (dipul)", "hint": "Geozonen beachten", "required": True},
    {"section": "Nach der Landung", "text": "Aufnahmen gesichert"},
]


@pytest.fixture
def service(setup):  # noqa: F811
    return ChecklistService(setup.incidents)


def test_only_landkreis_roles_manage_templates(setup, service) -> None:  # noqa: F811
    assert service.can_manage_templates(session(setup.auth, "kreis"))
    assert service.can_manage_templates(session(setup.auth, "betreiber"))
    assert not service.can_manage_templates(session(setup.auth, "sg-admin"))
    assert not service.can_manage_templates(session(setup.auth, "b-team"))
    with pytest.raises(ChecklistAccessError):
        service.create_template(session(setup.auth, "a-admin"), title="Eigene Vorlage", items=ITEMS)

    template = service.create_template(session(setup.auth, "kreis"), title="Vorflugkontrolle", items=ITEMS + [{"text": "  "}])
    assert template["item_count"] == 3 and template["required_count"] == 2 and template["version"] == 1
    changed = service.update_template(session(setup.auth, "kreis"), template["id"], items=ITEMS[:1])
    assert changed["version"] == 2


def test_wehr_templates_are_private_and_reusable(setup, service) -> None:  # noqa: F811
    team = session(setup.auth, "b-team")
    b = setup.ids["b"]
    shared = service.create_template(session(setup.auth, "kreis"), title="Landkreis", items=ITEMS)
    own = service.create_template(team, organization_id=b, title="Gerätewagen", items=ITEMS)
    assert service.template_owners(team) == [b]
    assert {item["title"]: item["can_manage"] for item in service.visible_templates(team)} == {
        "Gerätewagen": True, "Landkreis": False,
    }
    assert [item["title"] for item in service.visible_templates(session(setup.auth, "a-admin"))] == ["Landkreis"]
    viewer = session(setup.auth, "b-zuschauer")
    assert service.template_owners(viewer) == []
    with pytest.raises(ChecklistAccessError):
        service.update_template(viewer, own["id"], title="x")
    with pytest.raises(ChecklistAccessError):
        service.update_template(team, shared["id"], title="x")
    with pytest.raises(ChecklistAccessError):
        service.create_template(team, organization_id=setup.ids["a"], title="Fremd")
    # Fremde Wehren können die Liste weder lesen, ändern noch durchführen.
    other = session(setup.auth, "a-admin")
    with pytest.raises(LookupError):
        service.require_template(other, own["id"])
    with pytest.raises(LookupError):
        service.delete_template(other, own["id"])
    with pytest.raises(ChecklistError):
        service.create(other, organization_id=setup.ids["a"], template_id=own["id"])
    for _ in range(2):
        assert service.create(team, organization_id=b, template_id=own["id"])["done"] == 0


def test_wehr_creates_own_list_without_template(setup, service) -> None:  # noqa: F811
    team = session(setup.auth, "b-team")
    own = service.create(team, organization_id=setup.ids["b"], title="Gerätecheck Drohne 1",
                         items=[{"text": "Propeller geprüft", "required": True}])
    assert own["template_id"] is None and own["can"]["edit"]
    with pytest.raises(ChecklistAccessError):
        service.create(team, organization_id=setup.ids["a"], title="Fremd")
    # Andere Wehren sehen die Liste nicht.
    assert not service.access(session(setup.auth, "a-admin"), own)["view"]
    assert [item["id"] for item in service.visible(session(setup.auth, "b-zuschauer"))] == [own["id"]]
    assert not service.access(session(setup.auth, "b-zuschauer"), own)["edit"]


def test_standalone_list_locks_after_completion(setup, service) -> None:  # noqa: F811
    team = session(setup.auth, "b-team")
    own = service.create(team, organization_id=setup.ids["b"], title="Wartung", items=ITEMS)
    item = own["items"][0]
    checked = service.set_item(team, own["id"], item["id"], checked=True, note="Alle 4 Akkus voll")
    entry = checked["items"][0]
    assert entry["checked"] and entry["checked_by"] == "b-team" and entry["note"] == "Alle 4 Akkus voll"
    assert checked["open_required"] == ["Luftraum geprüft (dipul)"]

    service.set_status(team, own["id"], "completed")
    with pytest.raises(ChecklistAccessError):
        service.set_item(team, own["id"], item["id"], checked=False)
    with pytest.raises(ChecklistAccessError):
        service.set_status(team, own["id"], "open")
    # Admin der Wehr (hier: Kreis-Admin) darf weiter ändern und wieder öffnen.
    service.set_item(session(setup.auth, "kreis"), own["id"], item["id"], note="Nachtrag")
    assert service.set_status(session(setup.auth, "kreis"), own["id"], "open")["status"] == "open"


def test_incident_checklist_from_template_locks_with_incident(setup, service) -> None:  # noqa: F811
    template = service.create_template(session(setup.auth, "kreis"), title="Vorflugkontrolle", items=ITEMS)
    incident = create(setup)
    team = session(setup.auth, "b-team")
    checklist = service.create(team, template_id=template["id"], incident_id=incident["id"])
    assert checklist["title"] == "Vorflugkontrolle" and checklist["template_version"] == 1
    assert len(checklist["items"]) == 3
    assert any("Checkliste „Vorflugkontrolle“" in entry["text"] for entry in setup.incidents.log(incident["id"]))

    # Beteiligte Wehr darf abhaken, solange der Einsatz läuft.
    setup.incidents.add_organization(team, incident["id"], setup.ids["a"])
    a_admin = session(setup.auth, "a-admin")
    service.set_item(a_admin, checklist["id"], checklist["items"][0]["id"], checked=True)

    setup.incidents.set_status(team, incident["id"], "ended")
    setup.incidents.set_status(session(setup.auth, "kreis"), incident["id"], "closed")
    with pytest.raises(ChecklistAccessError):
        service.set_item(team, checklist["id"], checklist["items"][1]["id"], checked=True)
    with pytest.raises(ChecklistAccessError):
        service.set_item(a_admin, checklist["id"], checklist["items"][1]["id"], checked=True)
    with pytest.raises(ChecklistError):
        service.set_status(team, checklist["id"], "completed")
    # Admin der führenden Wehr (Kreis-Admin ist Admin aller Wehren) darf noch ändern.
    done = service.set_item(session(setup.auth, "kreis"), checklist["id"], checklist["items"][1]["id"], checked=True)
    assert done["open_required"] == []


def test_documents_upload_and_access(setup, service, tmp_path: Path) -> None:  # noqa: F811
    store = DocumentStore(service, tmp_path / "documents")
    with pytest.raises(ChecklistAccessError):
        store.upload(session(setup.auth, "a-admin"), filename="merkblatt.pdf", data=b"%PDF-1.4")
    with pytest.raises(ChecklistError):
        store.upload(session(setup.auth, "kreis"), filename="skript.sh", data=b"echo")
    document = store.upload(session(setup.auth, "kreis"), filename="../Merkblatt Drohne.pdf",
                            data=b"%PDF-1.4 test", description="Stand 2026")
    assert document["original_name"] == "Merkblatt Drohne.pdf" and document["title"] == "Merkblatt Drohne"
    assert store.path(document).read_bytes() == b"%PDF-1.4 test"
    assert store.path(document).parent == tmp_path / "documents"
    store.delete(session(setup.auth, "kreis"), document["id"])
    assert not store.path(document).exists() and store.list() == []


def test_organizations_keep_their_own_documents(setup, service, tmp_path: Path) -> None:  # noqa: F811
    store = DocumentStore(service, tmp_path / "documents")
    team = session(setup.auth, "b-team")
    shared = store.upload(session(setup.auth, "kreis"), filename="kreis.pdf", data=b"%PDF")
    own = store.upload(team, filename="wehr.pdf", data=b"%PDF", organization_id=setup.ids["b"])
    with pytest.raises(ChecklistAccessError):
        store.upload(team, filename="x.pdf", data=b"%PDF", organization_id=setup.ids["a"])
    with pytest.raises(ChecklistAccessError):
        store.upload(session(setup.auth, "b-zuschauer"), filename="x.pdf", data=b"%PDF",
                     organization_id=setup.ids["b"])

    viewer = session(setup.auth, "b-zuschauer")
    assert {item["id"] for item in store.visible(viewer)} == {shared["id"], own["id"]}
    assert store.require(viewer, own["id"])["title"] == "wehr"
    other = session(setup.auth, "a-admin")
    assert [item["id"] for item in store.visible(other)] == [shared["id"]]
    for action in (store.require, store.delete):
        with pytest.raises(LookupError):
            action(other, own["id"])
    with pytest.raises(ChecklistAccessError):
        store.delete(team, shared["id"])
    assert own["id"] in {item["id"] for item in store.visible(session(setup.auth, "kreis"))}
    store.delete(team, own["id"])
    assert not store.path(own).exists()


def test_checklist_api_and_report(api, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    from open_bos_stream.api import checklists as checklists_api

    monkeypatch.setattr(checklists_api, "documents_directory", tmp_path / "documents")
    api.login("kreis")
    template = api.post("/api/checklists/templates", json={"title": "Vorflugkontrolle", "items": ITEMS}).json()["template"]

    api.login("b-team")
    overview = api.get("/api/checklists").json()
    assert overview["can_manage_templates"] is False
    assert [item["title"] for item in overview["templates"]] == ["Vorflugkontrolle"]
    assert api.post("/api/checklists/templates", json={"title": "X"}).status_code == 403

    incident_id = api.post("/api/incidents", json={"lead_organization_id": api.ids["b"], "keyword": "Suche"}).json()["incident"]["id"]
    assert api.get(f"/api/incidents/{incident_id}").json()["checklist_templates"][0]["id"] == template["id"]
    checklist = api.post("/api/checklists", json={"incident_id": incident_id, "template_id": template["id"]}).json()["checklist"]
    item_id = checklist["items"][0]["id"]
    updated = api.put(f"/api/checklists/{checklist['id']}/items/{item_id}", json={"checked": True, "note": "ok"}).json()
    assert updated["checklist"]["done"] == 1 and updated["checklist"]["incident"]["code"]

    detail = api.get(f"/api/incidents/{incident_id}").json()
    assert detail["checklists"][0]["open_required"] == ["Luftraum geprüft (dipul)"]
    report = api.get(f"/api/incidents/{incident_id}/report").text
    assert "Vorflugkontrolle" in report and "☑" in report and "(Pflicht, offen)" in report

    # Dokumente: Upload als Rohdaten, nur Landkreis.
    assert api.post("/api/documents?filename=a.pdf", content=b"%PDF").status_code == 403
    api.login("kreis")
    uploaded = api.post("/api/documents?filename=Merkblatt.pdf&title=Merkblatt", content=b"%PDF-1.4")
    assert uploaded.status_code == 200
    document_id = uploaded.json()["document"]["id"]
    api.login("b-zuschauer")
    listed = api.get("/api/documents").json()
    assert listed["owners"] == [] and listed["documents"][0]["title"] == "Merkblatt"
    assert listed["documents"][0]["can_manage"] is False and listed["documents"][0]["shared"]
    file = api.get(f"/api/documents/{document_id}/file?download=1")
    assert file.content == b"%PDF-1.4" and "attachment" in file.headers["content-disposition"]
