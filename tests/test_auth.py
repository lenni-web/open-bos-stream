from pathlib import Path

import pytest

from open_bos_stream.auth.service import AuthError, AuthService
from open_bos_stream.auth.middleware import SUPERADMIN_PATHS
from open_bos_stream.auth.middleware import SUPERADMIN_PREFIXES


def service(tmp_path: Path) -> AuthService:
    return AuthService(
        str(tmp_path / "users.yaml"),
        str(tmp_path / "auth.secret"),
    )


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


def test_superadmin_only_routes_cover_sensitive_features() -> None:
    assert "/display" in SUPERADMIN_PREFIXES
    assert "/web-access" in SUPERADMIN_PREFIXES
    assert "/stream-output" in SUPERADMIN_PREFIXES
    assert "/auth/users" in SUPERADMIN_PREFIXES
    assert "/config/restore" in SUPERADMIN_PATHS
