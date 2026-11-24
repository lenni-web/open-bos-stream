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


# Zuweisbare Benutzerrollen. "guest" ist keine Benutzerrolle, sondern
# entsteht nur über einen zeitlich begrenzten Gastlink.
ROLES = ("viewer", "admin", "superadmin")
ROLE_LEVEL = {
    role: index
    for index, role in enumerate(("guest", *ROLES))
}
GUEST_PREFIX = "__guest__:"

# Zeichen ohne Verwechslungsgefahr (kein 0/O, 1/I/l) für den Einrichtungscode.
SETUP_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class AuthError(ValueError):
    """Ungültige Anmeldung oder Benutzerkonfiguration."""


class AuthService:
    COOKIE_NAME = "open_bos_session"
    SESSION_SECONDS = 12 * 60 * 60

    def __init__(
        self,
        users_file: str = "config/users.yaml",
        secret_file: str = "config/auth.secret",
        setup_code_file: str | None = None,
        revoked_file: str | None = None,
    ) -> None:
        self.users_file = Path(users_file)
        # Wird vom Container gesetzt (auth/guest_links.py).
        self.guest_links = None
        self.secret_file = Path(secret_file)
        self.setup_code_file = Path(
            setup_code_file
            or self.users_file.with_name("setup.code")
        )
        self.revoked_file = Path(
            revoked_file
            or self.users_file.with_name("revoked_sessions.json")
        )
        self._users_cache: tuple[tuple[int, int], list[dict]] | None = None
        self._revoked_cache: tuple[tuple[int, int], dict[str, int]] | None = None
        self._secret_cache: bytes | None = None

    @property
    def configured(self) -> bool:
        return bool(self._read_users())

    @staticmethod
    def _file_key(path: Path) -> tuple[int, int] | None:
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        return (stat.st_mtime_ns, stat.st_size)

    def _read_users(self) -> list[dict]:
        # Jede Anfrage prüft die Sitzung; die Datei wird nur nach einer
        # Änderung neu gelesen.
        key = self._file_key(self.users_file)
        if key is None:
            self._users_cache = None
            return []
        if self._users_cache is None or self._users_cache[0] != key:
            with self.users_file.open(encoding="utf-8") as file:
                data = yaml.safe_load(file) or {}
            self._users_cache = (key, list(data.get("users", [])))
        return [dict(item) for item in self._users_cache[1]]

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
        if self._secret_cache is not None:
            return self._secret_cache
        if not self.secret_file.exists():
            self.secret_file.parent.mkdir(parents=True, exist_ok=True)
            self.secret_file.write_bytes(secrets.token_bytes(32))
            os.chmod(self.secret_file, 0o600)
        self._secret_cache = self.secret_file.read_bytes()
        return self._secret_cache

    # -----------------------------------------------------
    # Einrichtungscode für die Ersteinrichtung
    # -----------------------------------------------------

    def ensure_setup_code(self) -> str | None:
        """Code für die Ersteinrichtung bereitstellen, solange sie fehlt."""

        if self.configured:
            self.setup_code_file.unlink(missing_ok=True)
            return None
        if self.setup_code_file.exists():
            return self.setup_code_file.read_text(encoding="utf-8").strip()
        raw = "".join(
            secrets.choice(SETUP_CODE_ALPHABET) for _ in range(8)
        )
        code = f"{raw[:4]}-{raw[4:]}"
        self.setup_code_file.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            self.setup_code_file,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(code + "\n")
        return code

    @staticmethod
    def _normalize_setup_code(code: str) -> str:
        return "".join(
            character for character in code.upper() if character.isalnum()
        )

    def setup_code_valid(self, code: str | None) -> bool:
        if not code or not self.setup_code_file.exists():
            return False
        expected = self.setup_code_file.read_text(encoding="utf-8")
        return hmac.compare_digest(
            self._normalize_setup_code(code).encode(),
            self._normalize_setup_code(expected).encode(),
        )

    def complete_setup(
        self,
        username: str,
        password: str,
        setup_code: str | None,
    ) -> dict:
        """Ersten Superadmin nur mit gültigem Einrichtungscode anlegen."""

        if not self.setup_code_valid(setup_code):
            raise AuthError("Der Einrichtungscode ist ungültig.")
        user = self.create_user(
            username,
            password,
            "superadmin",
            initial=True,
        )
        self.setup_code_file.unlink(missing_ok=True)
        return user

    # -----------------------------------------------------
    # Widerrufene Sitzungen (Abmelden)
    # -----------------------------------------------------

    def _revoked(self) -> dict[str, int]:
        key = self._file_key(self.revoked_file)
        if key is None:
            self._revoked_cache = None
            return {}
        if self._revoked_cache is None or self._revoked_cache[0] != key:
            try:
                data = json.loads(self.revoked_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            self._revoked_cache = (
                key,
                {str(k): int(v) for k, v in dict(data).items()},
            )
        return self._revoked_cache[1]

    def revoke_token(self, token: str | None) -> None:
        """Eine Sitzung bis zu ihrem Ablauf serverseitig ungültig machen."""

        payload = self._verified_payload(token)
        if payload is None or not payload.get("jti"):
            return
        now = int(time.time())
        revoked = {
            jti: expires
            for jti, expires in self._revoked().items()
            if expires >= now
        }
        revoked[str(payload["jti"])] = int(payload["exp"])
        self.revoked_file.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=".revoked.",
            suffix=".tmp",
            dir=self.revoked_file.parent,
            text=True,
        )
        temporary_path = Path(temporary)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                json.dump(revoked, file)
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, self.revoked_file)
        finally:
            temporary_path.unlink(missing_ok=True)

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

    def create_token(
        self,
        user: dict,
        *,
        purpose: str = "session",
    ) -> str:
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
            "use": purpose,
            "jti": secrets.token_urlsafe(12),
            "exp": int(time.time()) + self.SESSION_SECONDS,
        }
        return self._sign(payload)

    def _sign(self, payload: dict) -> str:
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

    def create_guest_token(self, link, *, purpose: str = "session") -> str:
        """Sitzung für einen Gastlink; endet spätestens mit dem Link."""

        return self._sign({
            "sub": GUEST_PREFIX + link.id,
            "role": "guest",
            "stamp": "guest",
            "use": purpose,
            "jti": secrets.token_urlsafe(12),
            "exp": int(link.expires_at),
        })

    def _guest_user(self, payload: dict) -> dict | None:
        if payload.get("role") != "guest" or payload.get("stamp") != "guest":
            return None
        if self.guest_links is None:
            return None
        link = self.guest_links.active_link(payload["sub"][len(GUEST_PREFIX):])
        if link is None:
            return None
        return {
            "username": f"Gast: {link.label}",
            "role": "guest",
            "guest_link": link.id,
            "source_ids": list(link.source_ids),
            "expires_at": link.expires_at,
        }

    def create_display_token(self) -> str:
        return self.create_token({
            "username": "__display__",
            "role": "viewer",
        })

    def create_media_token(self, user: dict) -> str:
        """Kurzer Ausweis für direkte MediaMTX-Abrufe (WHEP/HLS)."""

        if user.get("role") == "guest":
            link = (
                self.guest_links.active_link(user.get("guest_link", ""))
                if self.guest_links is not None
                else None
            )
            if link is None:
                raise AuthError("Der Gastlink ist nicht mehr gültig.")
            return self.create_guest_token(link, purpose="media")

        username = (
            "__display__"
            if user.get("username") == "Lokales Display"
            else user["username"]
        )
        return self.create_token(
            {"username": username, "role": user["role"]},
            purpose="media",
        )

    def _verified_payload(self, token: str | None) -> dict | None:
        """Signatur und Ablauf prüfen; liefert die Nutzdaten."""

        if not token:
            return None
        try:
            raw_value, signature_value = token.split(".", 1)
            signature = base64.urlsafe_b64decode(
                signature_value + "=" * (-len(signature_value) % 4)
            )
            expected = hmac.new(
                self._secret(),
                raw_value.encode(),
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
            return payload
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def verify_token(
        self,
        token: str | None,
        *,
        purpose: str = "session",
    ) -> dict | None:
        payload = self._verified_payload(token)
        if payload is None:
            return None
        try:
            # Ältere Sitzungstoken tragen noch keinen Verwendungszweck.
            if payload.get("use", "session") != purpose:
                return None
            if payload.get("jti") and payload["jti"] in self._revoked():
                return None
            if str(payload.get("sub", "")).startswith(GUEST_PREFIX):
                return self._guest_user(payload)
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
        except (KeyError, TypeError):
            return None

    @staticmethod
    def has_role(user: dict | None, minimum: str) -> bool:
        if not user:
            return False
        return ROLE_LEVEL.get(user["role"], -1) >= ROLE_LEVEL[minimum]
