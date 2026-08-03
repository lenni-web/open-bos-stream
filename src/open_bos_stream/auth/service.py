"""Dateibasierte lokale Anmeldung mit signierten Sitzungscookies."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import time
from pathlib import Path

import yaml


ROLES = ("viewer", "admin", "superadmin")
ROLE_LEVEL = {role: index for index, role in enumerate(ROLES)}


class AuthError(ValueError):
    """Ungültige Anmeldung oder Benutzerkonfiguration."""


class AuthService:
    COOKIE_NAME = "open_bos_session"
    SESSION_SECONDS = 12 * 60 * 60

    def __init__(
        self,
        users_file: str = "config/users.yaml",
        secret_file: str = "config/auth.secret",
    ) -> None:
        self.users_file = Path(users_file)
        self.secret_file = Path(secret_file)

    @property
    def configured(self) -> bool:
        return bool(self._read_users())

    def _read_users(self) -> list[dict]:
        if not self.users_file.exists():
            return []
        with self.users_file.open(encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        return list(data.get("users", []))

    def _write_users(self, users: list[dict]) -> None:
        self.users_file.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=".users.",
            suffix=".tmp",
            dir=self.users_file.parent,
            text=True,
        )
        temporary_path = Path(temporary)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                yaml.safe_dump(
                    {"users": users},
                    file,
                    allow_unicode=True,
                    sort_keys=False,
                )
                file.flush()
                os.fsync(file.fileno())
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, self.users_file)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _secret(self) -> bytes:
        if not self.secret_file.exists():
            self.secret_file.parent.mkdir(parents=True, exist_ok=True)
            self.secret_file.write_bytes(secrets.token_bytes(32))
            os.chmod(self.secret_file, 0o600)
        return self.secret_file.read_bytes()

    @staticmethod
    def _normalize_username(username: str) -> str:
        value = username.strip().lower()
        if (
            not 3 <= len(value) <= 32
            or not value.replace("-", "").replace("_", "").isalnum()
        ):
            raise AuthError(
                "Benutzername: 3–32 Buchstaben, Zahlen, '-' oder '_'."
            )
        return value

    @staticmethod
    def _password_hash(password: str, salt: bytes | None = None) -> str:
        if len(password) < 10:
            raise AuthError("Das Passwort muss mindestens 10 Zeichen haben.")
        salt = salt or secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt,
            240_000,
        )
        return (
            "pbkdf2_sha256$240000$"
            f"{base64.urlsafe_b64encode(salt).decode()}$"
            f"{base64.urlsafe_b64encode(digest).decode()}"
        )

    @classmethod
    def _verify_password(cls, password: str, encoded: str) -> bool:
        try:
            algorithm, iterations, salt_value, digest_value = encoded.split("$")
            if algorithm != "pbkdf2_sha256":
                return False
            salt = base64.urlsafe_b64decode(salt_value)
            expected = base64.urlsafe_b64decode(digest_value)
            actual = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode(),
                salt,
                int(iterations),
            )
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False

    def create_user(
        self,
        username: str,
        password: str,
        role: str,
        *,
        initial: bool = False,
    ) -> dict:
        username = self._normalize_username(username)
        if role not in ROLES:
            raise AuthError("Unbekannte Rolle.")
        users = self._read_users()
        if initial:
            if users or role != "superadmin":
                raise AuthError("Die Ersteinrichtung ist bereits abgeschlossen.")
        elif any(item["username"] == username for item in users):
            raise AuthError("Dieser Benutzername ist bereits vergeben.")
        users.append({
            "username": username,
            "role": role,
            "password_hash": self._password_hash(password),
        })
        self._write_users(users)
        return {"username": username, "role": role}

    def authenticate(self, username: str, password: str) -> dict | None:
        username = username.strip().lower()
        for user in self._read_users():
            if (
                user.get("username") == username
                and self._verify_password(
                    password,
                    user.get("password_hash", ""),
                )
            ):
                return {
                    "username": username,
                    "role": user["role"],
                }
        return None

    def users(self) -> list[dict]:
        return [
            {"username": item["username"], "role": item["role"]}
            for item in self._read_users()
        ]

    def user(self, username: str) -> dict | None:
        """Öffentliche Kontodaten eines einzelnen Benutzers."""

        normalized = username.strip().lower()
        return next(
            (
                {
                    "username": item["username"],
                    "role": item["role"],
                }
                for item in self._read_users()
                if item["username"] == normalized
            ),
            None,
        )

    def delete_user(self, username: str, current_username: str) -> None:
        username = username.strip().lower()
        if username == current_username:
            raise AuthError("Das eigene Konto kann nicht gelöscht werden.")
        users = self._read_users()
        remaining = [
            item for item in users if item["username"] != username
        ]
        if len(remaining) == len(users):
            raise AuthError("Benutzer wurde nicht gefunden.")
        if not any(item["role"] == "superadmin" for item in remaining):
            raise AuthError("Mindestens ein Superadmin muss erhalten bleiben.")
        self._write_users(remaining)

    def update_user(
        self,
        username: str,
        *,
        role: str | None = None,
        password: str | None = None,
    ) -> dict:
        username = username.strip().lower()
        if role is not None and role not in ROLES:
            raise AuthError("Unbekannte Rolle.")
        users = self._read_users()
        target = next(
            (
                item for item in users
                if item["username"] == username
            ),
            None,
        )
        if target is None:
            raise AuthError("Benutzer wurde nicht gefunden.")
        if role is not None:
            target["role"] = role
        if password:
            target["password_hash"] = self._password_hash(password)
        if not any(item["role"] == "superadmin" for item in users):
            raise AuthError("Mindestens ein Superadmin muss erhalten bleiben.")
        self._write_users(users)
        return {"username": username, "role": target["role"]}

    def create_token(self, user: dict) -> str:
        if user["username"] == "__display__":
            stamp = "display"
        else:
            stored = next(
                (
                    item for item in self._read_users()
                    if item["username"] == user["username"]
                ),
                None,
            )
            if stored is None:
                raise AuthError("Benutzer wurde nicht gefunden.")
            stamp = hashlib.sha256(
                stored["password_hash"].encode()
            ).hexdigest()[:16]
        payload = {
            "sub": user["username"],
            "role": user["role"],
            "stamp": stamp,
            "exp": int(time.time()) + self.SESSION_SECONDS,
        }
        raw = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).rstrip(b"=")
        signature = hmac.new(
            self._secret(),
            raw,
            hashlib.sha256,
        ).digest()
        return (
            raw.decode()
            + "."
            + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
        )

    def create_display_token(self) -> str:
        return self.create_token({
            "username": "__display__",
            "role": "viewer",
        })

    def verify_token(self, token: str | None) -> dict | None:
        if not token:
            return None
        try:
            raw_value, signature_value = token.split(".", 1)
            raw = raw_value.encode()
            signature = base64.urlsafe_b64decode(
                signature_value + "=" * (-len(signature_value) % 4)
            )
            expected = hmac.new(
                self._secret(),
                raw,
                hashlib.sha256,
            ).digest()
            if not hmac.compare_digest(signature, expected):
                return None
            payload = json.loads(
                base64.urlsafe_b64decode(
                    raw_value + "=" * (-len(raw_value) % 4)
                )
            )
            if int(payload["exp"]) < int(time.time()):
                return None
            stored = next(
                (
                    item for item in self._read_users()
                    if item["username"] == payload["sub"]
                ),
                None,
            )
            current = (
                {
                    "username": "Lokales Display",
                    "role": "viewer",
                }
                if (
                    payload["sub"] == "__display__"
                    and payload["role"] == "viewer"
                )
                else (
                    {
                        "username": stored["username"],
                        "role": stored["role"],
                    }
                    if stored
                    else None
                )
            )
            if not current or current["role"] != payload["role"]:
                return None
            expected_stamp = (
                "display"
                if payload["sub"] == "__display__"
                else hashlib.sha256(
                    stored["password_hash"].encode()
                ).hexdigest()[:16]
            )
            if payload.get("stamp") != expected_stamp:
                return None
            return current
        except (ValueError, KeyError, json.JSONDecodeError):
            return None

    @staticmethod
    def has_role(user: dict | None, minimum: str) -> bool:
        if not user:
            return False
        return ROLE_LEVEL.get(user["role"], -1) >= ROLE_LEVEL[minimum]
