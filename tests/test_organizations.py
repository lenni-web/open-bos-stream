from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml
from fastapi import HTTPException

from open_bos_stream.auth.guest_access import (
    allowed_media_paths,
    can_admin_source,
    can_operate_source,
    can_see_source,
)
from open_bos_stream.auth.service import AuthService
from open_bos_stream.core.models import SourceConfig
from open_bos_stream.db.database import Database
from open_bos_stream.org.service import OrgError, OrgService


PASSWORD = "sicheres-passwort"


def source(source_id: str, organization_id: int | None) -> SourceConfig:
    return SourceConfig(
        id=source_id,
        name=f"Drohne {source_id}",
        type="rtmp",
        organization_id=organization_id,
    )


# ----------------------------------------------------------------------
# Aufbau: Landkreis (1) → Meine Feuerwehr (2), Samtgemeinde (3) → OF A (4),
# OF B (5) direkt unter dem Landkreis.
# ----------------------------------------------------------------------


def build(auth: AuthService) -> dict[str, int]:
    org = auth.ready()
    samtgemeinde = org.create_organization(
        name="Samtgemeindefeuerwehr Harsefeld",
        kind="samtgemeindefeuerwehr",
        parent_id=1,
    )["id"]
    of_a = org.create_organization(
        name="Ortsfeuerwehr A",
        short_name="OF A",
        kind="ortsfeuerwehr",
        parent_id=samtgemeinde,
    )["id"]
    of_b = org.create_organization(
        name="Ortsfeuerwehr B",
        kind="ortsfeuerwehr",
        parent_id=1,
    )["id"]
    auth.create_user("betreiber", PASSWORD, "superadmin", initial=True)
    auth.create_user("kreis", PASSWORD, "admin", organization_id=1)
    auth.create_user("sg-admin", PASSWORD, "admin", organization_id=samtgemeinde)
    auth.create_user("a-admin", PASSWORD, "admin", organization_id=of_a)
    auth.create_user("b-team", PASSWORD, "operator", organization_id=of_b)
    auth.create_user("b-zuschauer", PASSWORD, "viewer", organization_id=of_b)
    return {"root": 1, "start": 2, "sg": samtgemeinde, "a": of_a, "b": of_b}


@pytest.fixture
def auth(tmp_path: Path) -> AuthService:
    service = AuthService(
        str(tmp_path / "users.yaml"),
        str(tmp_path / "auth.secret"),
        database=Database(None),
    )
    return service


def session(auth: AuthService, username: str) -> dict:
    return auth.authenticate(username, PASSWORD)


# ----------------------------------------------------------------------
# Grundstruktur und Übernahme
# ----------------------------------------------------------------------


def test_base_structure_is_created_once(auth: AuthService) -> None:
    org = auth.ready()
    names = [(item["name"], item["kind"]) for item in org.organizations()]
    assert ("Landkreis", "landkreis") in names
    assert ("Meine Feuerwehr", "ortsfeuerwehr") in names
    org.ensure_base()
    assert len(org.organizations()) == 2


def test_legacy_users_are_imported_and_file_kept(tmp_path: Path) -> None:
    users_file = tmp_path / "users.yaml"
    hashed = AuthService._password_hash(PASSWORD)
    users_file.write_text(
        yaml.safe_dump({
            "users": [
                {"username": "leitung", "role": "superadmin", "password_hash": hashed},
                {"username": "verwalter", "role": "admin", "password_hash": hashed},
                {"username": "zuschauer", "role": "viewer", "password_hash": hashed},
            ]
        }),
        encoding="utf-8",
    )
    auth = AuthService(str(users_file), str(tmp_path / "auth.secret"), database=Database(None))

    leitung = auth.authenticate("leitung", PASSWORD)
    verwalter = auth.authenticate("verwalter", PASSWORD)
    zuschauer = auth.authenticate("zuschauer", PASSWORD)

    assert leitung["role"] == "superadmin" and leitung["server_admin"]
    # Bisherige Admins verwalten die Start-Wehr, nicht den ganzen Server.
    assert verwalter["role"] == "admin" and not verwalter["server_admin"]
    assert verwalter["org_admin"] == [2]
    assert zuschauer["role"] == "viewer" and zuschauer["org_view"] == [2]
    assert not users_file.exists()
    assert (tmp_path / "users.yaml.importiert").exists()


# ----------------------------------------------------------------------
# Rechte im Baum
# ----------------------------------------------------------------------


def test_roles_are_inherited_down_the_tree(auth: AuthService) -> None:
    ids = build(auth)

    kreis = session(auth, "kreis")
    sg = session(auth, "sg-admin")
    team = session(auth, "b-team")

    assert set(kreis["org_admin"]) == {1, 2, ids["sg"], ids["a"], ids["b"]}
    assert kreis["server_admin"] is True
    assert set(sg["org_admin"]) == {ids["sg"], ids["a"]}
    assert sg["server_admin"] is False
    assert team["role"] == "operator"
    assert team["org_operate"] == [ids["b"]] and team["org_admin"] == []


def test_sources_are_separated_by_organisation(auth: AuthService) -> None:
    ids = build(auth)
    drone_a = source("a1", ids["a"])
    drone_b = source("b1", ids["b"])
    shared = source("kreis", None)

    sg = session(auth, "sg-admin")
    viewer_b = session(auth, "b-zuschauer")
    team_b = session(auth, "b-team")

    assert can_see_source(sg, drone_a) and not can_see_source(sg, drone_b)
    assert can_admin_source(sg, drone_a) and not can_admin_source(sg, shared)
    assert can_see_source(viewer_b, drone_b) and can_see_source(viewer_b, shared)
    assert not can_operate_source(viewer_b, drone_b)
    assert can_operate_source(team_b, drone_b)


def test_media_paths_follow_visible_sources(auth: AuthService) -> None:
    ids = build(auth)

    class Config:
        sources = [source("a1", ids["a"]), source("b1", ids["b"])]

    paths = allowed_media_paths(session(auth, "b-zuschauer"), Config)
    assert Config.sources[1].viewer_path in paths
    assert Config.sources[0].viewer_path not in paths
    assert allowed_media_paths(session(auth, "betreiber"), Config) is None


def test_role_change_ends_old_sessions(auth: AuthService) -> None:
    ids = build(auth)
    token = auth.create_token(session(auth, "b-zuschauer"))
    user = auth.ready().user_by_username("b-zuschauer")

    auth.ready().set_membership(user["id"], ids["b"], "admin")

    assert auth.verify_token(token) is None


def test_inactive_accounts_cannot_sign_in(auth: AuthService) -> None:
    build(auth)
    org = auth.ready()
    user = org.user_by_username("b-team")
    org.update_user(user["id"], active=False)
    assert auth.authenticate("b-team", PASSWORD) is None


def test_last_superadmin_and_tree_rules(auth: AuthService) -> None:
    ids = build(auth)
    org = auth.ready()
    betreiber = org.user_by_username("betreiber")

    with pytest.raises(OrgError):
        org.update_user(betreiber["id"], platform_admin=False)
    with pytest.raises(OrgError):
        org.update_organization(ids["sg"], parent_id=ids["a"])
    with pytest.raises(OrgError):
        org.delete_organization(ids["sg"])
    with pytest.raises(OrgError):
        org.delete_organization(1)


def test_qualifications_track_validity(auth: AuthService) -> None:
    build(auth)
    org = auth.ready()
    user = org.user_by_username("b-team")
    org.add_qualification(user["id"], kind="a2", reference="DEU-RP-123",
                          valid_until=date.today() + timedelta(days=30))
    org.add_qualification(user["id"], kind="a1a3",
                          valid_until=date.today() - timedelta(days=1))

    items = {item["kind"]: item for item in org.qualifications(user["id"])}
    assert items["a2"]["valid"] is True
    assert items["a1a3"]["valid"] is False
    with pytest.raises(OrgError):
        org.add_qualification(user["id"], kind="unbekannt")


# ----------------------------------------------------------------------
# Quellen speichern (Wehr-Admins nur eigene)
# ----------------------------------------------------------------------


def test_wehr_admin_changes_only_own_sources(auth: AuthService) -> None:
    from open_bos_stream.api.config import merge_sources

    ids = build(auth)
    stored = [source("a1", ids["a"]), source("b1", ids["b"]), source("kreis", None)]
    sg = session(auth, "sg-admin")

    renamed = source("a1", ids["a"]).model_copy(update={"name": "Neu"})
    # Sichtbar (ohne Zuordnung), aber nicht verwaltbar: bleibt unverändert.
    shared = source("kreis", None).model_copy(update={"name": "Übernommen"})
    merged = merge_sources(sg, stored, [renamed, shared, source("a2", ids["a"])])

    assert [item.id for item in merged] == ["a1", "b1", "kreis", "a2"]
    assert merged[0].name == "Neu"
    assert merged[2].name == "Drohne kreis"

    with pytest.raises(HTTPException):
        merge_sources(sg, stored, [source("b2", ids["b"])])
    # Entfernen einer eigenen Quelle bleibt möglich.
    assert [item.id for item in merge_sources(sg, stored, [])] == ["b1", "kreis"]


# ----------------------------------------------------------------------
# Schnittstelle
# ----------------------------------------------------------------------


@pytest.fixture
def api(auth: AuthService, tmp_path: Path, monkeypatch):
    from fastapi.testclient import TestClient

    from open_bos_stream.core import container
    from open_bos_stream.core.event_log import ServerEventLog
    from open_bos_stream.api import organizations as organizations_api
    from open_bos_stream.main import app

    real = container.auth_service
    for name in ("org", "_ready", "users_file", "secret_file", "revoked_file", "_secret_cache"):
        monkeypatch.setattr(real, name, getattr(auth, name))
    monkeypatch.setattr(organizations_api, "server_event_log", ServerEventLog(None))
    ids = build(real)
    client = TestClient(app)

    def login(username: str) -> None:
        client.cookies.clear()
        client.cookies.set(
            real.COOKIE_NAME,
            real.create_token(real.authenticate(username, PASSWORD)),
        )

    client.login = login
    client.ids = ids
    return client


def test_wehr_admin_manages_only_own_branch(api) -> None:
    ids = api.ids
    api.login("sg-admin")

    created = api.post("/api/org/organizations", json={
        "name": "Ortsfeuerwehr C", "kind": "ortsfeuerwehr", "parent_id": ids["sg"],
    })
    assert created.status_code == 200
    assert api.post("/api/org/organizations", json={
        "name": "Fremd", "kind": "ortsfeuerwehr", "parent_id": ids["b"],
    }).status_code == 403
    assert api.post("/api/org/organizations", json={
        "name": "Zweiter Landkreis", "kind": "landkreis", "parent_id": None,
    }).status_code == 403

    usernames = {item["username"] for item in api.get("/api/org/users").json()["users"]}
    assert usernames == {"sg-admin", "a-admin"}

    assert api.post("/api/org/users", json={
        "username": "neu-a", "password": PASSWORD,
        "organization_id": ids["a"], "role": "operator",
    }).status_code == 200
    assert api.post("/api/org/users", json={
        "username": "neu-b", "password": PASSWORD,
        "organization_id": ids["b"], "role": "viewer",
    }).status_code == 403


def test_superadmin_flag_and_foreign_accounts_are_protected(api) -> None:
    ids = api.ids
    api.login("kreis")
    users = {item["username"]: item for item in api.get("/api/org/users").json()["users"]}

    assert api.patch(
        f"/api/org/users/{users['b-team']['id']}",
        json={"platform_admin": True},
    ).status_code == 403
    assert api.patch(
        f"/api/org/users/{users['betreiber']['id']}",
        json={"display_name": "x"},
    ).status_code == 403

    api.login("sg-admin")
    # Konto auch in OF B: nur Rollen im eigenen Bereich, keine Kontodaten.
    assert api.put(
        f"/api/org/users/{users['b-team']['id']}/memberships/{ids['a']}",
        json={"role": "viewer"},
    ).status_code == 200
    assert api.patch(
        f"/api/org/users/{users['b-team']['id']}",
        json={"display_name": "x"},
    ).status_code == 403


def test_server_wide_settings_need_kreis_admin(api) -> None:
    api.login("sg-admin")
    assert api.get("/api/weather/settings").status_code == 403
    assert api.get("/system/info").status_code == 403

    api.login("kreis")
    assert api.get("/api/weather/settings").status_code == 200


def test_operator_may_create_guest_links_only_for_own_sources(api, monkeypatch, tmp_path) -> None:
    from open_bos_stream.core import container

    ids = api.ids
    monkeypatch.setattr(
        container.config,
        "sources",
        [source("a1", ids["a"]), source("b1", ids["b"])],
    )
    from open_bos_stream.api import guest as guest_api
    from open_bos_stream.auth.guest_links import GuestLinkStore
    from open_bos_stream.core.event_log import ServerEventLog

    monkeypatch.setattr(guest_api, "guest_link_store", GuestLinkStore(tmp_path / "links.json"))
    monkeypatch.setattr(guest_api, "server_event_log", ServerEventLog(None))

    api.login("b-zuschauer")
    assert api.get("/guest-links").status_code == 403

    api.login("b-team")
    ok = api.post("/guest-links", json={"label": "Polizei", "source_ids": ["b1"], "hours": 2})
    assert ok.status_code == 200
    assert ok.json()["link"]["organization_id"] == ids["b"]
    assert api.post(
        "/guest-links", json={"label": "Fremd", "source_ids": ["a1"], "hours": 2}
    ).status_code == 403

    api.login("a-admin")
    assert api.get("/guest-links").json()["links"] == []


def test_dashboard_hides_other_organisations(api, monkeypatch) -> None:
    from open_bos_stream.api import dashboard as dashboard_api
    from open_bos_stream.core import container
    from open_bos_stream.core.event_log import ServerEventLog

    ids = api.ids
    monkeypatch.setattr(
        container.config,
        "sources",
        [source("a1", ids["a"]), source("b1", ids["b"])],
    )
    monkeypatch.setattr(
        container.dashboard_service,
        "status",
        lambda: {
            "sources": [{"id": "a1"}, {"id": "b1"}],
            "recordings": [{"source_id": "a1"}, {"source_id": "b1"}],
            "stream_outputs": [],
        },
    )
    log = ServerEventLog(None)
    log.record("info", "System")
    log.record("info", "Signal A", organization_id=ids["a"])
    log.record("info", "Signal B", organization_id=ids["b"])
    monkeypatch.setattr(dashboard_api, "server_event_log", log)

    api.login("a-admin")
    data = api.get("/dashboard/status").json()
    assert [item["id"] for item in data["sources"]] == ["a1"]
    assert [item["source_id"] for item in data["recordings"]] == ["a1"]
    assert [item["message"] for item in data["server_events"]["events"]] == ["Signal A"]
    assert api.post("/dashboard/sources/b1/fullscreen").status_code == 403

    api.login("kreis")
    messages = [item["message"] for item in api.get("/dashboard/status").json()["server_events"]["events"]]
    assert messages == ["System", "Signal A", "Signal B"]


def test_hidden_foreign_id_is_reported_not_dropped(auth: AuthService) -> None:
    from open_bos_stream.api.config import merge_sources

    ids = build(auth)
    stored = [source("quelle-1", 2)]  # Start-Wehr, für SG-Admin unsichtbar
    sg = session(auth, "sg-admin")

    with pytest.raises(HTTPException) as error:
        merge_sources(sg, stored, [source("quelle-1", ids["a"])])
    assert error.value.status_code == 409


def test_migrations_and_module_files_are_packaged() -> None:
    """Der Server nutzt das installierte Paket; Nicht-Python-Dateien müssen
    ausdrücklich in den Paketdaten stehen."""

    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    for pattern in (
        '"db/migrations/*.py"',
        '"db/migrations/script.py.mako"',
        '"db/migrations/versions/*.py"',
        '"static/vendor/maplibre/*.mjs"',
    ):
        assert pattern in pyproject
