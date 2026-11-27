"""Lokale Anmeldung mit signierten Sitzungscookies.

Konten, Organisationen und Rollen liegen in der Datenbank (siehe
open_bos_stream.org). Die frühere Datei config/users.yaml wird beim ersten
Start übernommen und danach als users.yaml.importiert aufbewahrt.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from open_bos_stream.db.database import Database
from open_bos_stream.incidents.service import IncidentService
from open_bos_stream.org.service import OrgError, OrgService


# Grobe Rollen für Seiten und Schnittstellen. Sie ergeben sich aus der
# höchsten Rolle in einer Organisation; "superadmin" ist die technische
# Plattformrolle. "guest" entsteht nur über einen Gastlink.
ROLES = ("viewer", "operator", "admin", "superadmin")
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
        database: Database | None = None,
    ) -> None:
        self.users_file = Path(users_file)
        self.org = OrgService(
            database or Database(self.users_file.with_name("open-bos.db"))
        )
        self._ready = False
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
        self._revoked_cache: tuple[tuple[int, int], dict[str, int]] | None = None
        self._secret_cache: bytes | None = None
        self._incidents: IncidentService | None = None

    @property
    def incidents(self) -> IncidentService:
        """Einsätze in derselben Datenbank wie die Organisationen."""

        if self._incidents is None or self._incidents.org is not self.org:
            self._incidents = IncidentService(self.org)
        return self._incidents

    def ready(self) -> OrgService:
        """Datenbank migrieren, Grundstruktur anlegen, alte Konten übernehmen."""

        if not self._ready:
            self.org.db.migrate()
            self.org.ensure_base()
            self._import_legacy_users()
            self._ready = True
        return self.org

    def _import_legacy_users(self) -> None:
        if self.org.user_count() or not self.users_file.exists():
            return
        try:
            with self.users_file.open(encoding="utf-8") as file:
                data = yaml.safe_load(file) or {}
        except (OSError, yaml.YAMLError):
            return
        root_id = min(self.org.root_ids())
        start_id = self.org.default_organization_id()
        for item in data.get("users", []):
            role = item.get("role")
            created = self.org.create_user(
                username=item["username"],
                password_hash=item["password_hash"],
                platform_admin=role == "superadmin",
                actor="Übernahme",
            )
            if role == "superadmin":
                # Betreiber des Servers: zugleich Kreis-Admin.
                self.org.set_membership(created["id"], root_id, "admin", actor="Übernahme")
            elif role in {"admin", "viewer"}:
                self.org.set_membership(created["id"], start_id, role, actor="Übernahme")
        self.users_file.replace(
            self.users_file.with_name(self.users_file.name + ".importiert")
        )

    @property
    def configured(self) -> bool:
        return bool(self.ready().user_count())

    @staticmethod
    def _file_key(path: Path) -> tuple[int, int] | None:
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        return (stat.st_mtime_ns, stat.st_size)

    def _session_user(self, stored: dict) -> dict:
        """Kontodaten einer Sitzung samt Rechten in Organisationen."""

        org = self.ready()
        scope = org.scope(stored).as_dict()
        incident_sources = self.incidents.running_source_ids(scope)
        return {
            "username": stored["username"],
            "role": org.effective_role(stored),
            "user_id": stored["id"],
            "display_name": stored.get("display_name") or stored["username"],
            **scope,
            # Drohnen laufender Einsätze der eigenen bzw. beteiligten Wehren.
            "incident_source_ids": incident_sources,
        }

    def session_user_for(self, user_id: int) -> dict | None:
        """Aktuelle Rechte eines aktiven Kontos (z. B. für Push-Empfänger)."""

        stored = self.ready().user_by_id(user_id)
        if not stored or not stored.get("active", True):
            return None
        return self._session_user(stored)

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
        organization_id: int | None = None,
        display_name: str = "",
        email: str = "",
        actor: str = "",
    ) -> dict:
        """Konto anlegen; Rolle gilt in der angegebenen Organisation.

        "superadmin" legt ein Konto mit Plattformrolle an, das zugleich
        Kreis-Admin ist. Ohne Organisation gilt die Start-Organisation.
        """

        username = self._normalize_username(username)
        if role not in ROLES:
            raise AuthError("Unbekannte Rolle.")
        org = self.ready()
        if initial and (org.user_count() or role != "superadmin"):
            raise AuthError("Die Ersteinrichtung ist bereits abgeschlossen.")
        try:
            created = org.create_user(
                username=username,
                password_hash=self._password_hash(password),
                display_name=display_name,
                email=email,
                platform_admin=role == "superadmin",
                actor=actor,
            )
            if role == "superadmin":
                org.set_membership(created["id"], min(org.root_ids()), "admin", actor=actor)
            else:
                org.set_membership(
                    created["id"],
                    organization_id or org.default_organization_id(),
                    role,
                    actor=actor,
                )
        except OrgError as exc:
            raise AuthError(str(exc)) from exc
        return {"username": username, "role": role, "user_id": created["id"]}

    def authenticate(self, username: str, password: str) -> dict | None:
        stored = self.ready().user_by_username(username.strip().lower())
        if (
            stored
            and stored["active"]
            and self._verify_password(password, stored["password_hash"])
        ):
            self.org.update_user(
                stored["id"],
                last_login_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
            return self._session_user(stored)
        return None

    def users(self) -> list[dict]:
        org = self.ready()
        return [
            {"username": item["username"], "role": org.effective_role(item)}
            for item in org.users()
        ]

    def user(self, username: str) -> dict | None:
        """Öffentliche Kontodaten eines einzelnen Benutzers."""

        org = self.ready()
        stored = org.user_by_username(username.strip().lower())
        if stored is None:
            return None
        return {"username": stored["username"], "role": org.effective_role(stored)}

    def delete_user(self, username: str, current_username: str) -> None:
        username = username.strip().lower()
        if username == current_username:
            raise AuthError("Das eigene Konto kann nicht gelöscht werden.")
        org = self.ready()
        stored = org.user_by_username(username)
        if stored is None:
            raise AuthError("Benutzer wurde nicht gefunden.")
        try:
            org.delete_user(stored["id"], actor=current_username)
        except OrgError as exc:
            raise AuthError(str(exc)) from exc

    def set_password(self, user_id: int, password: str, *, actor: str = "") -> None:
        try:
            self.ready().update_user(
                user_id,
                password_hash=self._password_hash(password),
                actor=actor,
            )
        except OrgError as exc:
            raise AuthError(str(exc)) from exc

    def update_user(
        self,
        username: str,
        *,
        role: str | None = None,
        password: str | None = None,
    ) -> dict:
        """Vereinfachte Änderung (Rolle in der Start-Organisation)."""

        username = username.strip().lower()
        if role is not None and role not in ROLES:
            raise AuthError("Unbekannte Rolle.")
        org = self.ready()
        stored = org.user_by_username(username)
        if stored is None:
            raise AuthError("Benutzer wurde nicht gefunden.")
        try:
            if role == "superadmin":
                org.update_user(stored["id"], platform_admin=True)
            elif role is not None:
                org.update_user(stored["id"], platform_admin=False)
                org.set_membership(stored["id"], org.default_organization_id(), role)
            if password:
                org.update_user(
                    stored["id"],
                    password_hash=self._password_hash(password),
                )
        except OrgError as exc:
            raise AuthError(str(exc)) from exc
        return self.user(username)

    def create_token(
        self,
        user: dict,
        *,
        purpose: str = "session",
    ) -> str:
        if user["username"] == "__display__":
            stamp = "display"
        else:
            stored = self.ready().user_by_username(user["username"])
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
        user = {
            "username": f"Gast: {link.label}",
            "role": "guest",
            "guest_link": link.id,
            "source_ids": list(link.source_ids),
            "expires_at": link.expires_at,
        }
        if link.incident_id is not None:
            incident = self.incidents.get(link.incident_id)
            # Einsatz-Gastlinks enden spätestens mit dem Einsatz.
            if incident is None or incident["status"] != "running":
                return None
            user["incident_id"] = incident["id"]
            user["source_ids"] = self.incidents.active_source_ids(incident["id"])
        return user

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
            stored = (
                None
                if payload["sub"] == "__display__"
                else self.ready().user_by_username(payload["sub"])
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
                    self._session_user(stored)
                    if stored and stored["active"]
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
