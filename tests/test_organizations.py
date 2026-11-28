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
from open_bos_stream.auth.service import AuthError, AuthService
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
        "first_name": "Anna", "last_name": "Alpha",
        "organization_id": ids["a"], "role": "operator",
    }).status_code == 200
    assert api.post("/api/org/users", json={
        "username": "neu-b", "password": PASSWORD,
        "first_name": "Bernd", "last_name": "Beta",
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


def test_hidden_source_profiles_cannot_be_chosen_anew(auth: AuthService) -> None:
    from open_bos_stream.api.config import merge_sources

    ids = build(auth)
    kept = source("a1", ids["a"]).model_copy(update={"profile": "transcode"})
    sg = session(auth, "sg-admin")
    hidden = ["transcode"]

    # Bestehende Drohnen behalten ihr verstecktes Profil.
    renamed = kept.model_copy(update={"name": "Neu"})
    assert merge_sources(sg, [kept], [renamed], hidden_profiles=hidden)[0].name == "Neu"

    new = source("a2", ids["a"]).model_copy(update={"profile": "transcode"})
    switched = source("a1", ids["a"]).model_copy(update={"profile": "transcode"})
    for stored, incoming in (([], [new]), ([source("a1", ids["a"])], [switched])):
        with pytest.raises(HTTPException) as error:
            merge_sources(sg, stored, incoming, hidden_profiles=hidden)
        assert error.value.status_code == 422


def test_at_least_one_source_profile_stays_released() -> None:
    from open_bos_stream.core.models import SOURCE_PROFILE_IDS, check_hidden_profiles

    assert check_hidden_profiles(["transcode", "unbekannt"]) == ["transcode"]
    with pytest.raises(ValueError):
        check_hidden_profiles(list(SOURCE_PROFILE_IDS))


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
    # Ereignisprotokoll seit 0.25.4 nur für Superadmins.
    assert "server_events" not in data
    api.login("betreiber")
    events = api.get("/dashboard/status").json()["server_events"]["events"]
    assert [item["message"] for item in events] == ["System", "Signal A", "Signal B"]
    api.login("a-admin")
    assert api.post("/dashboard/sources/b1/fullscreen").status_code == 403

    # Auch Kreis-Admins sehen das Protokoll nicht mehr (nur Superadmins).
    api.login("kreis")
    assert "server_events" not in api.get("/dashboard/status").json()


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


def test_own_account_profile_and_password(api) -> None:
    api.login("b-team")
    me = api.get("/api/org/me").json()["user"]
    assert me["username"] == "b-team"
    assert me["memberships"][0]["role_label"] == "Drohnenteam"
    assert me["memberships"][0]["organization_name"] == "Ortsfeuerwehr B"

    updated = api.patch("/api/org/me", json={"display_name": "  Bea  Team ", "email": "bea@example.org"})
    assert updated.json()["user"]["display_name"] == "Bea Team"
    assert api.patch("/api/org/me", json={"email": "kaputt"}).status_code == 422

    assert api.patch("/api/org/me", json={
        "current_password": "falsch-falsch", "new_password": "neues-passwort-1",
    }).status_code == 403
    old_cookie = api.cookies.get("open_bos_session")
    changed = api.patch("/api/org/me", json={
        "current_password": PASSWORD, "new_password": "neues-passwort-1",
    })
    assert changed.status_code == 200 and changed.json()["password_changed"]
    # Diese Sitzung bleibt angemeldet (neues Cookie), die alte ist ungültig.
    assert api.get("/api/org/me").status_code == 200
    api.cookies.clear()
    api.cookies.set("open_bos_session", old_cookie)
    assert api.get("/api/org/me").status_code == 401


def test_accounts_have_first_last_and_nickname(api) -> None:
    api.login("sg-admin")
    missing = api.post("/api/org/users", json={
        "username": "ohne-name", "password": PASSWORD,
        "organization_id": api.ids["a"], "role": "viewer",
    })
    assert missing.status_code == 422
    created = api.post("/api/org/users", json={
        "username": "m-muster", "password": PASSWORD,
        "first_name": "  Max ", "last_name": "Mustermann", "nickname": "Maxi",
        "organization_id": api.ids["a"], "role": "operator",
    }).json()["user"]
    assert (created["first_name"], created["last_name"], created["nickname"]) == ("Max", "Mustermann", "Maxi")
    assert created["display_name"] == "Max Mustermann"

    renamed = api.patch(f"/api/org/users/{created['id']}", json={"last_name": "Muster-Meyer"}).json()["user"]
    assert renamed["display_name"] == "Max Muster-Meyer"

    api.login("b-team")
    own = api.patch("/api/org/me", json={"first_name": "Bea", "last_name": "Team", "nickname": "B."}).json()["user"]
    assert own["display_name"] == "Bea Team" and own["nickname"] == "B."
    assert api.patch("/api/org/me", json={"first_name": "  "}).status_code == 422


def test_ortsbrandmeister_has_admin_rights_in_own_ortswehr(auth) -> None:
    ids = build(auth)
    org = auth.ready()
    auth.create_user("a-obm", PASSWORD, "ortsbrandmeister", organization_id=ids["a"])
    user = org.user_by_username("a-obm")

    scope = org.scope(user)
    assert scope.admin == {ids["a"]}
    assert not scope.server_admin
    assert org.effective_role(user) == "admin"


def test_ortsbrandmeister_only_in_ortsfeuerwehr(auth) -> None:
    ids = build(auth)
    org = auth.ready()
    with pytest.raises(AuthError):
        auth.create_user("sg-obm", PASSWORD, "ortsbrandmeister", organization_id=ids["sg"])
    assert org.user_by_username("sg-obm") is None

    team = org.user_by_username("b-team")
    with pytest.raises(OrgError):
        org.set_membership(team["id"], ids["sg"], "ortsbrandmeister")
    org.set_membership(team["id"], ids["b"], "ortsbrandmeister")
    with pytest.raises(OrgError):
        org.update_organization(ids["b"], kind="kreiseinheit")


def test_organisations_can_be_moved_within_kind_rules(auth: AuthService) -> None:
    ids = build(auth)
    org = auth.ready()
    loose = org.create_organization(name="Ortsfeuerwehr D", kind="ortsfeuerwehr", parent_id=1)

    moved = org.update_organization(loose["id"], parent_id=ids["sg"])
    assert moved["parent_id"] == ids["sg"]
    assert loose["id"] in org.descendants([ids["sg"]])
    assert org.audit_entries()[0]["action"] == "Organisation verschoben"

    with pytest.raises(OrgError):  # Ortswehr unter Ortswehr
        org.update_organization(loose["id"], parent_id=ids["a"])
    with pytest.raises(OrgError):  # Samtgemeinde nur unter dem Landkreis
        org.create_organization(
            name="SG X", kind="samtgemeindefeuerwehr", parent_id=ids["sg"]
        )
    with pytest.raises(OrgError):  # Untereinheiten passen nicht mehr
        org.update_organization(ids["sg"], kind="kreiseinheit")


# ----------------------------------------------------------------------
# Anmeldung mit E-Mail-Adresse
# ----------------------------------------------------------------------


def test_login_with_email_and_unique_addresses(auth: AuthService) -> None:
    build(auth)
    org = auth.ready()
    first = auth.create_user(
        "eva", PASSWORD, "viewer", email="Eva@Example.org"
    )["user_id"]

    assert auth.authenticate(" eva@example.ORG ", PASSWORD)["username"] == "eva"
    assert auth.authenticate("eva@example.org", "falsches-passwort") is None
    assert auth.authenticate("niemand@example.org", PASSWORD) is None
    assert auth.login_name("EVA@example.org") == "eva"

    with pytest.raises(AuthError):
        auth.create_user("zweite", PASSWORD, "viewer", email="eva@example.org")
    assert org.user_by_username("zweite") is None
    other = auth.create_user("otto", PASSWORD, "viewer")["user_id"]
    with pytest.raises(OrgError):
        org.update_user(other, email="eva@example.org")
    # Das eigene Konto darf die Adresse behalten.
    org.update_user(first, email="eva@example.org")


def test_duplicate_legacy_email_only_blocks_email_login(auth: AuthService) -> None:
    from sqlalchemy import update

    from open_bos_stream.db.schema import users

    build(auth)
    org = auth.ready()
    with org.db.engine.begin() as connection:
        connection.execute(
            update(users)
            .where(users.c.username.in_(["kreis", "sg-admin"]))
            .values(email="wache@example.org")
        )

    assert auth.authenticate("wache@example.org", PASSWORD) is None
    assert auth.authenticate("kreis", PASSWORD)
    # Unverändert speichern bleibt möglich.
    org.update_user(org.user_by_username("kreis")["id"], email="wache@example.org")


def test_email_conflict_changes_nothing_and_lock_is_per_account(api) -> None:
    from open_bos_stream.core.container import auth_service, login_rate_limiter

    org = auth_service.ready()
    org.update_user(org.user_by_username("kreis")["id"], email="kreis@example.org")
    target = org.user_by_username("b-zuschauer")

    api.login("kreis")
    response = api.patch(f"/api/org/users/{target['id']}", json={
        "email": "kreis@example.org", "password": "neues-passwort-123",
    })
    assert response.status_code == 409
    assert auth_service.authenticate("b-zuschauer", PASSWORD)

    api.login("b-zuschauer")
    response = api.patch("/api/org/me", json={"email": "kreis@example.org"})
    assert response.status_code == 409

    # Name und Adresse zählen zusammen; sonst wären es doppelt so viele Versuche.
    api.cookies.clear()
    try:
        for name in ["kreis", "kreis@example.org"] * 3:
            response = api.post("/auth/login", json={"username": name, "password": "falsch"})
        assert response.status_code == 429
    finally:
        login_rate_limiter.record_success("kreis", "testclient")


# ----------------------------------------------------------------------
# Mehrere Rollen je Organisation
# ----------------------------------------------------------------------


def roles_in(org: OrgService, user_id: int, organization_id: int) -> list[str]:
    return [
        item["role"] for item in org.memberships(user_id)
        if item["organization_id"] == organization_id
    ]


def test_several_roles_in_one_organisation(auth: AuthService) -> None:
    ids = build(auth)
    org = auth.ready()
    user = org.user_by_username("b-team")

    org.set_roles(user["id"], ids["b"], ["operator", "ortsbrandmeister"])
    assert roles_in(org, user["id"], ids["b"]) == ["ortsbrandmeister", "operator"]
    assert org.effective_role(user) == "admin"
    assert org.scope(user).admin == {ids["b"]}

    # Ohne den Titel bleiben nur die Rechte des Drohnenteams.
    org.set_roles(user["id"], ids["b"], ["operator"])
    assert org.effective_role(user) == "operator"
    assert not org.scope(user).admin

    # Ungültige Auswahl ändert nichts.
    for wrong in ([], ["operator", "chef"]):
        with pytest.raises(OrgError):
            org.set_roles(user["id"], ids["b"], wrong)
    with pytest.raises(OrgError):
        org.set_roles(user["id"], ids["sg"], ["viewer", "ortsbrandmeister"])
    assert roles_in(org, user["id"], ids["b"]) == ["operator"]
    assert roles_in(org, user["id"], ids["sg"]) == []

    org.set_roles(user["id"], ids["b"], ["operator", "viewer"])
    org.remove_membership(user["id"], ids["b"])
    assert roles_in(org, user["id"], ids["b"]) == []


def test_roles_api_and_member_count(api) -> None:
    from open_bos_stream.core.container import auth_service

    ids = api.ids
    org = auth_service.ready()
    user = org.user_by_username("b-team")
    url = f"/api/org/users/{user['id']}/memberships/{ids['b']}"
    api.login("kreis")

    def count() -> int:
        items = api.get("/api/org/organizations").json()["organizations"]
        return next(item["member_count"] for item in items if item["id"] == ids["b"])

    before = count()
    response = api.put(url, json={"roles": ["operator", "ortsbrandmeister"]})
    assert response.status_code == 200
    assert [item["role"] for item in response.json()["user"]["memberships"]] == [
        "ortsbrandmeister", "operator",
    ]
    assert count() == before
    assert api.put(url, json={"roles": []}).status_code == 409


def test_migration_keeps_roles_and_allows_a_second_one(tmp_path: Path) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    from open_bos_stream.db.database import MIGRATIONS

    database = Database(tmp_path / "alt.db")
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    with database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0007_drones")
        connection.execute(text(
            "INSERT INTO organizations (id, name, short_name, kind, archived, created_at) "
            "VALUES (1, 'OF', '', 'ortsfeuerwehr', 0, '2026-01-01')"
        ))
        connection.execute(text(
            "INSERT INTO users (id, username, display_name, email, password_hash, "
            "platform_admin, active, created_at) "
            "VALUES (1, 'alt', '', '', 'x', 0, 1, '2026-01-01')"
        ))
        connection.execute(text(
            "INSERT INTO memberships (user_id, organization_id, role) VALUES (1, 1, 'operator')"
        ))

    database.migrate()
    org = OrgService(database)
    assert roles_in(org, 1, 1) == ["operator"]
    org.set_roles(1, 1, ["operator", "ortsbrandmeister"])

    # Zurück: je Organisation bleibt die höchste Rolle.
    with database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0007_drones")
        assert connection.execute(text("SELECT role FROM memberships")).scalars().all() == [
            "ortsbrandmeister"
        ]
