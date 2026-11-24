from __future__ import annotations

import asyncio
import stat
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from open_bos_stream.auth.guest_access import media_uri_allowed
from open_bos_stream.auth.guest_links import (
    GuestLinkError,
    GuestLinkStore,
    RETENTION_SECONDS,
)
from open_bos_stream.auth.service import AuthError, AuthService


def store_in(tmp_path: Path) -> GuestLinkStore:
    return GuestLinkStore(tmp_path / "guest_links.json")


# ----------------------------------------------------------------------
# Speicher
# ----------------------------------------------------------------------


def test_link_is_stored_only_as_hash_with_private_permissions(tmp_path) -> None:
    store = store_in(tmp_path)
    link, token = store.create(
        label="Polizei Stade",
        source_ids=["quelle-1"],
        hours=8,
        created_by="einsatzleiter",
    )
    content = (tmp_path / "guest_links.json").read_text()
    assert token not in content
    assert link.token_hash in content
    mode = stat.S_IMODE((tmp_path / "guest_links.json").stat().st_mode)
    assert mode == 0o600
    assert store.find_by_token(token).id == link.id
    assert store.find_by_token(token + "x") is None
    assert len(token) >= 32


@pytest.mark.parametrize(
    ("hours", "source_ids", "label"),
    [
        (49, ["quelle-1"], "Zu lang"),
        (0, ["quelle-1"], "Null"),
        (2, [], "Ohne Quelle"),
        (2, ["quelle-1"], "   "),
    ],
)
def test_invalid_links_are_rejected(tmp_path, hours, source_ids, label) -> None:
    with pytest.raises(GuestLinkError):
        store_in(tmp_path).create(
            label=label,
            source_ids=source_ids,
            hours=hours,
            created_by="admin",
        )


def test_revoked_and_expired_links_stop_working(tmp_path, monkeypatch) -> None:
    store = store_in(tmp_path)
    revoked, revoked_token = store.create(
        label="A", source_ids=["q"], hours=2, created_by="admin"
    )
    expiring, expiring_token = store.create(
        label="B", source_ids=["q"], hours=1, created_by="admin"
    )

    store.revoke(revoked.id, "zweiter-admin")
    assert store.find_by_token(revoked_token) is None
    assert store.active_link(revoked.id) is None
    listed = {link.id: link for link in store.list()}
    assert listed[revoked.id].revoked_by == "zweiter-admin"

    now = time.time()
    monkeypatch.setattr(time, "time", lambda: now + 3601)
    assert store.find_by_token(expiring_token) is None
    assert expiring.id in {link.id for link in store.list()}

    # Nach der Aufbewahrungsfrist verschwinden alte Links aus der Liste.
    monkeypatch.setattr(time, "time", lambda: now + 3600 * 2 + RETENTION_SECONDS + 1)
    assert store.list() == []


def test_media_uri_check_accepts_only_released_streams() -> None:
    paths = {"quelle-1", "quelle-1-view"}
    assert media_uri_allowed("/whep/quelle-1-view/whep", paths)
    assert media_uri_allowed("/quelle-1-view/whep", paths)
    assert media_uri_allowed("/hls/quelle-1/index.m3u8?token=x", paths)
    assert media_uri_allowed("/quelle-1-view/whep/0d3f-secret", paths)
    assert not media_uri_allowed("/whep/quelle-2-view/whep", paths)
    assert not media_uri_allowed("/quelle-2/index.m3u8", paths)
    assert not media_uri_allowed("", paths)
    assert not media_uri_allowed("/whep", paths)


# ----------------------------------------------------------------------
# Sitzungen
# ----------------------------------------------------------------------


def auth_in(tmp_path: Path) -> tuple[AuthService, GuestLinkStore]:
    auth = AuthService(
        users_file=str(tmp_path / "users.yaml"),
        secret_file=str(tmp_path / "auth.secret"),
    )
    store = store_in(tmp_path)
    auth.guest_links = store
    return auth, store


def test_guest_session_and_media_token(tmp_path) -> None:
    auth, store = auth_in(tmp_path)
    link, _ = store.create(
        label="Polizei", source_ids=["quelle-1"], hours=2, created_by="admin"
    )
    session = auth.create_guest_token(link)
    user = auth.verify_token(session)
    assert user["role"] == "guest"
    assert user["source_ids"] == ["quelle-1"]
    assert user["username"] == "Gast: Polizei"

    media = auth.create_media_token(user)
    assert auth.verify_token(media, purpose="media")["role"] == "guest"
    # Ein Medien-Token taugt nicht als Sitzung und umgekehrt.
    assert auth.verify_token(media) is None
    assert auth.verify_token(session, purpose="media") is None

    store.revoke(link.id, "admin")
    assert auth.verify_token(session) is None
    assert auth.verify_token(media, purpose="media") is None
    with pytest.raises(AuthError):
        auth.create_media_token(user)


def test_guest_is_not_an_assignable_user_role(tmp_path) -> None:
    auth, _ = auth_in(tmp_path)
    with pytest.raises(AuthError):
        auth.create_user("gast", "langes-passwort-123", "guest")


def test_guest_session_ends_with_link_expiry(tmp_path, monkeypatch) -> None:
    auth, store = auth_in(tmp_path)
    link, _ = store.create(
        label="Kurz", source_ids=["quelle-1"], hours=1, created_by="admin"
    )
    session = auth.create_guest_token(link)
    now = time.time()
    monkeypatch.setattr(time, "time", lambda: now + 3601)
    assert auth.verify_token(session) is None


# ----------------------------------------------------------------------
# Schnittstellen
# ----------------------------------------------------------------------


@pytest.fixture
def guest_env(tmp_path, monkeypatch):
    from open_bos_stream.api import guest as guest_api
    from open_bos_stream.core import container
    from open_bos_stream.main import app

    auth = container.auth_service
    store = store_in(tmp_path)
    monkeypatch.setattr(auth, "guest_links", store)
    monkeypatch.setattr(guest_api, "guest_link_store", store)
    monkeypatch.setattr(auth, "secret_file", tmp_path / "auth.secret")
    monkeypatch.setattr(auth, "_secret_cache", None)
    monkeypatch.setattr(auth, "revoked_file", tmp_path / "revoked.json")
    monkeypatch.setattr(
        type(auth), "configured", property(lambda self: True)
    )
    source_id = container.config.sources[0].id
    link, token = store.create(
        label="Polizei", source_ids=[source_id], hours=2, created_by="admin"
    )
    return TestClient(app), store, link, token, source_id


def test_guest_link_opens_reduced_view_only(guest_env, monkeypatch) -> None:
    client, _, _, token, source_id = guest_env
    from open_bos_stream.core.container import auth_service, dashboard_service

    response = client.get(f"/g/{token}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/guest"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "samesite=lax" in cookie.lower()
    client.cookies.set(
        auth_service.COOKIE_NAME,
        response.cookies[auth_service.COOKIE_NAME],
    )

    assert client.get("/", follow_redirects=False).headers["location"] == "/guest"
    assert client.get("/dashboard/status").status_code == 403
    assert client.get("/config/").status_code == 403
    assert client.get("/recording/files").status_code == 403
    assert client.get("/guest-links").status_code == 403
    page = client.get("/guest")
    assert page.status_code == 200
    assert "Gastzugang" in page.text

    monkeypatch.setattr(
        dashboard_service,
        "status",
        lambda: {
            "sources": [
                {"id": source_id, "name": "Erlaubt", "ready": True,
                 "publish_url": "rtmp://geheim", "runtime": {"pid": 1}},
                {"id": "andere", "name": "Verboten", "ready": True},
            ]
        },
    )
    status = client.get("/guest/status").json()
    assert [item["id"] for item in status["sources"]] == [source_id]
    assert status["sources"][0]["publish_url"] == ""
    assert "runtime" not in status["sources"][0]


def test_invalid_guest_link_shows_friendly_page(guest_env) -> None:
    client = guest_env[0]
    response = client.get("/g/falsch", follow_redirects=False)
    assert response.status_code == 410
    assert "nicht mehr gültig" in response.text


def test_guest_media_access_is_limited_to_released_sources(guest_env) -> None:
    client, store, link, token, source_id = guest_env
    from open_bos_stream.core.container import auth_service, config

    source = next(item for item in config.sources if item.id == source_id)
    client.cookies.set(
        auth_service.COOKIE_NAME,
        auth_service.create_guest_token(link),
    )

    def access(uri: str) -> int:
        return client.get(
            "/auth/media-access",
            headers={"X-Forwarded-Uri": uri},
        ).status_code

    assert access(f"/whep/{source.viewer_path}/whep") == 204
    assert access("/whep/fremde-quelle-view/whep") == 403
    assert client.post(
        "/dashboard/sources/fremde-quelle/fullscreen"
    ).status_code == 403

    store.revoke(link.id, "admin")
    assert access(f"/whep/{source.viewer_path}/whep") == 401


def test_mediamtx_reader_check_for_guest_tokens(guest_env) -> None:
    _, _, link, _, source_id = guest_env
    from open_bos_stream.api import mediamtx_auth
    from open_bos_stream.api.mediamtx_auth import MediaMTXAuthRequest
    from open_bos_stream.core.container import auth_service, config

    source = next(item for item in config.sources if item.id == source_id)
    token = auth_service.create_guest_token(link, purpose="media")
    local = Request({
        "type": "http",
        "method": "POST",
        "path": "/internal/mediamtx/auth",
        "headers": [],
        "client": ("127.0.0.1", 40000),
    })

    def read(path: str):
        return asyncio.run(
            mediamtx_auth.authorize_mediamtx(
                MediaMTXAuthRequest(
                    action="read",
                    path=path,
                    protocol="webrtc",
                    ip="203.0.113.5",
                    token=token,
                ),
                local,
            )
        )

    assert read(source.viewer_path) == {"authorized": True}
    with pytest.raises(Exception) as denied:
        read("fremde-quelle-view")
    assert getattr(denied.value, "status_code", None) == 401


def test_admin_can_create_list_and_revoke(guest_env, monkeypatch) -> None:
    client, _, _, _, source_id = guest_env
    from open_bos_stream.core.container import auth_service

    def fake_verify(token, *, purpose="session"):
        if purpose == "session" and token in {"viewer", "admin"}:
            return {"username": token, "role": token}
        return None

    monkeypatch.setattr(auth_service, "verify_token", fake_verify)
    client.cookies.set(auth_service.COOKIE_NAME, "viewer")
    assert client.post(
        "/guest-links",
        json={"label": "X", "source_ids": [source_id], "hours": 2},
    ).status_code == 403

    client.cookies.set(auth_service.COOKIE_NAME, "admin")
    too_long = client.post(
        "/guest-links",
        json={"label": "X", "source_ids": [source_id], "hours": 72},
    )
    assert too_long.status_code == 422
    unknown = client.post(
        "/guest-links",
        json={"label": "X", "source_ids": ["gibt-es-nicht"], "hours": 2},
    )
    assert unknown.status_code == 422

    created = client.post(
        "/guest-links",
        json={"label": "Kreisbrandmeister", "source_ids": [source_id], "hours": 24},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert "/g/" in body["url"]
    assert "token_hash" not in body["link"]

    listing = client.get("/guest-links").json()["links"]
    assert listing[0]["label"] == "Kreisbrandmeister"
    assert body["url"].rsplit("/", 1)[1] not in str(listing)

    revoked = client.delete(f"/guest-links/{body['link']['id']}")
    assert revoked.json()["link"]["revoked_by"] == "admin"


def test_guest_link_does_not_replace_existing_login(guest_env, monkeypatch) -> None:
    client, _, _, token, _ = guest_env
    from open_bos_stream.core.container import auth_service

    original = auth_service.verify_token

    def fake_verify(value, *, purpose="session"):
        if value == "admin":
            return {"username": "einsatzleiter", "role": "admin"}
        return original(value, purpose=purpose)

    monkeypatch.setattr(auth_service, "verify_token", fake_verify)
    client.cookies.set(auth_service.COOKIE_NAME, "admin")
    response = client.get(f"/g/{token}", follow_redirects=False)
    assert response.status_code == 409
    assert "Bereits angemeldet" in response.text
    assert "set-cookie" not in response.headers
