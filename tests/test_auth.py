import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from open_bos_stream.api.auth import _assert_admin_scope
from open_bos_stream.auth.middleware import AuthMiddleware
from open_bos_stream.auth.middleware import PUBLIC_PREFIXES
from open_bos_stream.auth.roles import ADMIN, SUPERADMIN, route_roles
from open_bos_stream.auth.service import ROLE_LEVEL
from open_bos_stream.auth.service import AuthError, AuthService
from open_bos_stream.auth.rate_limit import LoginRateLimiter
from open_bos_stream.display.ticket import issue_ticket


class EndpointRoleService:
    COOKIE_NAME = "test_session"
    SESSION_SECONDS = 60
    configured = True

    @staticmethod
    def verify_token(token: str | None) -> dict | None:
        if token not in {"viewer", "admin", "superadmin"}:
            return None
        return {"username": token, "role": token}

    @staticmethod
    def has_role(user: dict | None, minimum: str) -> bool:
        return AuthService.has_role(user, minimum)


def system_admin_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(AuthMiddleware, service=EndpointRoleService())

    @app.get("/system/stream-log", dependencies=[ADMIN])
    async def stream_log():
        return {"content": "test"}

    @app.post("/system/reboot", dependencies=[SUPERADMIN])
    async def reboot():
        return {"success": True}

    return TestClient(app)


def service(tmp_path: Path) -> AuthService:
    return AuthService(
        str(tmp_path / "users.yaml"),
        str(tmp_path / "auth.secret"),
    )


def test_login_rate_limit_locks_and_recovers() -> None:
    now = [1000.0]
    limiter = LoginRateLimiter(
        account_limit=3,
        ip_limit=10,
        window_seconds=60,
        lock_seconds=120,
        clock=lambda: now[0],
    )

    assert limiter.record_failure("Leitung", "192.0.2.1") == 0
    assert limiter.record_failure("leitung", "192.0.2.1") == 0
    assert limiter.record_failure("leitung", "192.0.2.1") == 120
    assert limiter.retry_after("leitung", "192.0.2.1") == 120

    now[0] += 121
    assert limiter.retry_after("leitung", "192.0.2.1") == 0


def test_success_clears_account_failures_but_not_ip_protection() -> None:
    limiter = LoginRateLimiter(account_limit=2, ip_limit=3)

    limiter.record_failure("leitung", "192.0.2.1")
    limiter.record_success("leitung", "192.0.2.1")

    assert limiter.retry_after("leitung", "192.0.2.1") == 0
    assert limiter.record_failure("anderer", "192.0.2.1") == 0
    assert limiter.record_failure("dritter", "192.0.2.1") > 0


def test_initial_superadmin_and_signed_session(tmp_path: Path) -> None:
    auth = service(tmp_path)
    user = auth.create_user(
        "leitung",
        "sicheres-passwort",
        "superadmin",
        initial=True,
    )

    token = auth.create_token(user)

    assert auth.configured is True
    assert auth.authenticate(
        "leitung",
        "sicheres-passwort",
    ) == user
    assert auth.verify_token(token) == user
    assert auth.verify_token(token + "x") is None
    assert auth.verify_token(auth.create_display_token()) == {
        "username": "Lokales Display",
        "role": "viewer",
    }
    assert auth.users_file.stat().st_mode & 0o777 == 0o600


def test_roles_and_last_superadmin_are_protected(tmp_path: Path) -> None:
    auth = service(tmp_path)
    auth.create_user(
        "leitung",
        "sicheres-passwort",
        "superadmin",
        initial=True,
    )
    auth.create_user("operator", "anderes-passwort", "admin")
    auth.create_user("anzeige", "viewer-passwort", "viewer")

    assert AuthService.has_role(
        {"username": "operator", "role": "admin"},
        "admin",
    )
    assert not AuthService.has_role(
        {"username": "operator", "role": "admin"},
        "superadmin",
    )

    auth.delete_user("operator", "leitung")
    with pytest.raises(AuthError):
        auth.delete_user("leitung", "anzeige")


def test_user_role_and_password_can_be_updated(tmp_path: Path) -> None:
    auth = service(tmp_path)
    auth.create_user(
        "leitung",
        "sicheres-passwort",
        "superadmin",
        initial=True,
    )
    user = auth.create_user(
        "operator",
        "anderes-passwort",
        "viewer",
    )
    old_token = auth.create_token(user)

    updated = auth.update_user(
        "operator",
        role="admin",
        password="ganz-neues-passwort",
    )

    assert updated == {"username": "operator", "role": "admin"}
    assert auth.authenticate(
        "operator",
        "ganz-neues-passwort",
    ) == updated
    assert auth.authenticate("operator", "anderes-passwort") is None
    assert auth.verify_token(old_token) is None


def test_last_superadmin_cannot_be_demoted(tmp_path: Path) -> None:
    auth = service(tmp_path)
    auth.create_user(
        "leitung",
        "sicheres-passwort",
        "superadmin",
        initial=True,
    )

    with pytest.raises(AuthError):
        auth.update_user("leitung", role="admin")


def test_duplicate_user_and_short_password_are_rejected(
    tmp_path: Path,
) -> None:
    auth = service(tmp_path)
    auth.create_user(
        "leitung",
        "sicheres-passwort",
        "superadmin",
        initial=True,
    )

    with pytest.raises(AuthError):
        auth.create_user("leitung", "anderes-passwort", "viewer")
    with pytest.raises(AuthError):
        auth.create_user("neu", "kurz", "viewer")


def _required_role(route) -> str:
    """Strengste deklarierte Rolle einer Route."""

    roles = route_roles(route)
    if roles == ["public"]:
        return "public"
    return max(
        (role for role in roles if role != "public"),
        key=lambda role: ROLE_LEVEL[role],
    )


def _api_routes(routes=None) -> list:
    """Alle API-Routen, auch aus eingebundenen Routern."""

    from fastapi.routing import APIRoute

    from open_bos_stream.main import app

    found = []
    for route in app.routes if routes is None else routes:
        original = getattr(route, "original_router", None)
        if original is not None:
            found.extend(_api_routes(original.routes))
        elif isinstance(route, APIRoute):
            found.append(route)
    return found


def _application_routes() -> dict[tuple[str, str], str]:
    return {
        (method, route.path): _required_role(route)
        for route in _api_routes()
        for method in route.methods
    }


def test_every_route_declares_a_role() -> None:
    routes = _api_routes()
    undeclared = [
        f"{sorted(route.methods)} {route.path}"
        for route in routes
        if not route_roles(route)
    ]

    assert len(routes) > 60
    assert undeclared == []


def test_route_roles_are_enforced_over_http(monkeypatch) -> None:
    from open_bos_stream.core.container import auth_service
    from open_bos_stream.main import app

    def fake_verify(token, *, purpose="session"):
        if purpose == "session" and token in ROLE_LEVEL:
            return {"username": token, "role": token}
        return None

    monkeypatch.setattr(auth_service, "verify_token", fake_verify)
    monkeypatch.setattr(type(auth_service), "configured", property(lambda self: True))
    client = TestClient(app)

    def status(method: str, path: str, role: str | None) -> int:
        client.cookies.clear()
        if role:
            client.cookies.set(auth_service.COOKIE_NAME, role)
        return client.request(method, path).status_code

    assert status("GET", "/recording/files", None) == 401
    assert status("GET", "/recording/files", "viewer") == 403
    assert status("GET", "/recording/files", "admin") == 403
    assert status("GET", "/recording/files", "superadmin") == 200
    assert status("PUT", "/config/storage", "admin") == 403
    assert status("PUT", "/config/", "admin") == 403
    assert status("GET", "/system/stream-log", "viewer") == 403
    assert status("GET", "/stream/inputs", "viewer") == 403


@pytest.mark.parametrize(
    ("method", "path", "role"),
    [
        ("GET", "/", "viewer"),
        ("GET", "/login", "public"),
        ("POST", "/auth/setup", "public"),
        ("POST", "/auth/login", "public"),
        ("GET", "/auth/media-access", "guest"),
        ("GET", "/auth/media-token", "guest"),
        ("GET", "/auth/users", "admin"),
        ("POST", "/auth/users", "admin"),
        ("GET", "/dashboard/status", "viewer"),
        ("POST", "/dashboard/sources/{source_id}/fullscreen", "guest"),
        ("DELETE", "/dashboard/sources/{source_id}/fullscreen/{lease_id}", "guest"),
        ("POST", "/dashboard/sources/{source_id}/probe", "admin"),
        ("GET", "/dashboard/diagnostics", "admin"),
        ("GET", "/config/", "admin"),
        ("PUT", "/config/", "superadmin"),
        ("PUT", "/config/sources", "admin"),
        ("PUT", "/config/storage", "superadmin"),
        ("PUT", "/config/media-capture", "superadmin"),
        ("POST", "/config/restore", "superadmin"),
        ("GET", "/config/notifications", "superadmin"),
        ("PUT", "/config/notifications", "superadmin"),
        ("POST", "/config/notifications/test", "superadmin"),
        ("GET", "/stream/status", "viewer"),
        ("POST", "/stream/start", "admin"),
        ("GET", "/stream/inputs", "admin"),
        ("GET", "/system/stream-log", "admin"),
        ("POST", "/system/reboot", "superadmin"),
        ("GET", "/recording/files", "superadmin"),
        ("GET", "/snapshot/files", "superadmin"),
        ("GET", "/media/files", "superadmin"),
        ("GET", "/stream-output/status", "superadmin"),
        ("GET", "/display/status", "superadmin"),
        ("GET", "/web-access/status", "superadmin"),
        ("GET", "/api/map/maps", "guest"),
        ("GET", "/g/{token}", "public"),
        ("GET", "/guest", "guest"),
        ("GET", "/guest/status", "guest"),
        ("GET", "/guest-links", "admin"),
        ("POST", "/guest-links", "admin"),
        ("DELETE", "/guest-links/{link_id}", "admin"),
        ("POST", "/internal/mediamtx/auth", "public"),
    ],
)
def test_route_role_matrix(method: str, path: str, role: str) -> None:
    assert _application_routes()[(method, path)] == role


def test_stream_log_endpoint_requires_admin() -> None:
    with system_admin_client() as client:
        assert client.get("/system/stream-log").status_code == 401
        client.cookies.set("test_session", "viewer")
        assert client.get("/system/stream-log").status_code == 403
        for role in ("admin", "superadmin"):
            client.cookies.set("test_session", role)
            assert client.get("/system/stream-log").status_code == 200


def test_reboot_endpoint_requires_superadmin() -> None:
    with system_admin_client() as client:
        assert client.post("/system/reboot").status_code == 401
        for role in ("viewer", "admin"):
            client.cookies.set("test_session", role)
            assert client.post("/system/reboot").status_code == 403
        client.cookies.set("test_session", "superadmin")
        assert client.post("/system/reboot").status_code == 200


def test_caddy_media_check_is_not_public() -> None:
    assert not "/auth/media-access".startswith(PUBLIC_PREFIXES)


def test_admin_cannot_manage_or_create_superadmins() -> None:
    request = SimpleNamespace(
        state=SimpleNamespace(
            user={"username": "operator", "role": "admin"}
        )
    )

    with pytest.raises(HTTPException) as target_error:
        _assert_admin_scope(request, target_role="superadmin")
    with pytest.raises(HTTPException) as role_error:
        _assert_admin_scope(request, desired_role="superadmin")

    assert target_error.value.status_code == 403
    assert role_error.value.status_code == 403
    _assert_admin_scope(
        request,
        target_role="admin",
        desired_role="viewer",
    )


class DisplayTokenService(EndpointRoleService):
    @staticmethod
    def create_display_token() -> str:
        return "viewer"


def local_display_client(tmp_path: Path, monkeypatch) -> tuple[TestClient, str]:
    ticket_path = tmp_path / "kiosk-ticket"
    monkeypatch.setenv("OPEN_BOS_DISPLAY_TICKET_FILE", str(ticket_path))
    ticket = issue_ticket(ticket_path)

    app = FastAPI()
    app.add_middleware(AuthMiddleware, service=DisplayTokenService())

    @app.get("/")
    async def index():
        return {"page": "dashboard"}

    client = TestClient(
        app,
        client=("127.0.0.1", 50000),
        follow_redirects=False,
    )
    return client, ticket


def test_loopback_display_requires_valid_ticket(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, ticket = local_display_client(tmp_path, monkeypatch)

    # Über den Port-80-Proxy des lokalen Profils kommen auch fremde
    # Clients scheinbar von 127.0.0.1. Ohne Ticket keine Display-Sitzung.
    without_ticket = client.get(
        "/?display=1",
        headers={"accept": "text/html"},
    )
    wrong_ticket = client.get(
        "/?display=1&display_ticket=falsch",
        headers={"accept": "text/html"},
    )

    assert without_ticket.status_code == 303
    assert "test_session" not in without_ticket.cookies
    assert wrong_ticket.status_code == 303
    assert "test_session" not in wrong_ticket.cookies

    granted = client.get(f"/?display=1&display_ticket={ticket}")

    assert granted.status_code == 200
    assert granted.cookies.get("test_session") == "viewer"


def test_setup_requires_one_time_code(tmp_path: Path) -> None:
    auth = service(tmp_path)

    code = auth.ensure_setup_code()

    assert code and len(code) == 9
    assert auth.setup_code_file.stat().st_mode & 0o777 == 0o600
    assert auth.ensure_setup_code() == code
    with pytest.raises(AuthError):
        auth.complete_setup("leitung", "sicheres-passwort", None)
    with pytest.raises(AuthError):
        auth.complete_setup("leitung", "sicheres-passwort", "FALSCH-00")
    assert not auth.configured

    # Groß-/Kleinschreibung und Trennzeichen spielen keine Rolle.
    user = auth.complete_setup(
        "leitung",
        "sicheres-passwort",
        code.lower().replace("-", " "),
    )

    assert user == {"username": "leitung", "role": "superadmin"}
    assert not auth.setup_code_file.exists()
    assert auth.ensure_setup_code() is None
    with pytest.raises(AuthError):
        auth.complete_setup("zweiter", "sicheres-passwort", code)


def test_logout_revokes_only_that_session(tmp_path: Path) -> None:
    auth = service(tmp_path)
    user = auth.create_user("leitung", "sicheres-passwort", "superadmin")
    first = auth.create_token(user)
    second = auth.create_token(user)

    auth.revoke_token(first)

    assert auth.verify_token(first) is None
    assert auth.verify_token(second) == user
    # Ein zweiter Dienst (Neustart) liest den Widerruf aus der Datei.
    assert service(tmp_path).verify_token(first) is None


def test_media_and_session_tokens_are_not_interchangeable(tmp_path: Path) -> None:
    auth = service(tmp_path)
    user = auth.create_user("leitung", "sicheres-passwort", "viewer")
    session = auth.create_token(user)
    media = auth.create_media_token(user)

    assert auth.verify_token(media) is None
    assert auth.verify_token(session, purpose="media") is None
    assert auth.verify_token(media, purpose="media") == user
    display = auth.create_media_token({"username": "Lokales Display", "role": "viewer"})
    assert auth.verify_token(display, purpose="media")["role"] == "viewer"


def test_shared_local_proxy_does_not_lock_out_everybody() -> None:
    limiter = LoginRateLimiter(account_limit=5, ip_limit=20)

    for index in range(30):
        limiter.record_failure(f"benutzer{index}", "127.0.0.1")

    # Ohne IP-weite Sperre bleibt ein anderes Konto über denselben Proxy nutzbar.
    assert limiter.retry_after("leitung", "127.0.0.1") == 0
    for _ in range(5):
        limiter.record_failure("leitung", "127.0.0.1")
    assert limiter.retry_after("leitung", "127.0.0.1") > 0
    # Externe Adressen behalten die IP-weite Grenze.
    for index in range(20):
        limiter.record_failure(f"benutzer{index}", "203.0.113.9")
    assert limiter.retry_after("neu", "203.0.113.9") > 0


def test_session_cookie_is_secure_only_over_https(tmp_path, monkeypatch) -> None:
    from open_bos_stream.api import auth as auth_api

    auth = service(tmp_path)
    auth.create_user("leitung", "sicheres-passwort", "superadmin")
    monkeypatch.setattr(auth_api, "auth_service", auth)
    monkeypatch.setattr(auth_api, "login_rate_limiter", LoginRateLimiter())
    app = FastAPI()
    app.include_router(auth_api.router)
    credentials = {"username": "leitung", "password": "sicheres-passwort"}

    for base_url, secure in (("https://ffw-stream.test", True), ("http://pi.local", False)):
        response = TestClient(app, base_url=base_url).post(
            "/auth/login",
            json=credentials,
        )
        cookie = response.headers["set-cookie"].lower()
        assert response.status_code == 200
        assert ("; secure" in cookie) is secure


def test_admins_receive_masked_stream_output_urls(monkeypatch) -> None:
    from open_bos_stream.api import config as config_api

    def request_for(role: str):
        return SimpleNamespace(state=SimpleNamespace(user={"username": role, "role": role}))

    admin_view = asyncio.run(config_api.get_config(request_for("admin")))
    superadmin_view = asyncio.run(config_api.get_config(request_for("superadmin")))

    assert [output.url for output in admin_view.stream_outputs] == [
        "rtmp://stream.example.test:1935/***",
        "srt://srt.example.test:8890/***",
    ]
    assert superadmin_view.stream_outputs[0].url.endswith("/live/test")
