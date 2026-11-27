"""Organisationsbaum, Konten, Mitgliedschaften und Fernpilotennachweise.

Rechte vererben sich im Baum nach unten: Eine Rolle in einer
Organisation gilt auch für alle Organisationen darunter. Eine Rolle in
der obersten Organisation (Landkreis) gilt damit im ganzen Landkreis.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from open_bos_stream.db.database import Database
from open_bos_stream.db.schema import (
    MEMBERSHIP_ROLES,
    ORGANIZATION_KINDS,
    QUALIFICATION_KINDS,
    audit_log,
    memberships,
    organizations,
    qualifications,
    users,
)


ROLE_ORDER = ("viewer", "operator", "admin")
DEFAULT_ROOT_NAME = "Landkreis"
DEFAULT_START_NAME = "Meine Feuerwehr"


class OrgError(ValueError):
    """Ungültige Änderung an Organisationen oder Konten."""


NAME_LIMITS = {"first_name": 60, "last_name": 60, "nickname": 40}


def clean_name(value, limit: int) -> str:
    """Name ohne Steuerzeichen und überzählige Leerzeichen."""

    text = " ".join("".join(ch for ch in str(value or "") if ch.isprintable()).split())
    return text[:limit]


def compose_display_name(first_name: str, last_name: str, fallback: str = "") -> str:
    full = f"{first_name} {last_name}".strip()
    return (full or fallback.strip())[:80]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def role_at_least(role: str, minimum: str) -> bool:
    return ROLE_ORDER.index(role) >= ROLE_ORDER.index(minimum)


@dataclass
class Scope:
    """Wo ein Konto welche Rolle hat (Organisationen inklusive Unterbaum)."""

    view: set[int] = field(default_factory=set)
    operate: set[int] = field(default_factory=set)
    admin: set[int] = field(default_factory=set)
    # Kreis-Admin oder Superadmin: serverweite Einstellungen.
    server_admin: bool = False
    platform_admin: bool = False

    def as_dict(self) -> dict:
        return {
            "org_view": sorted(self.view),
            "org_operate": sorted(self.operate),
            "org_admin": sorted(self.admin),
            "server_admin": self.server_admin,
            "platform_admin": self.platform_admin,
        }


class OrgService:
    def __init__(self, database: Database) -> None:
        self.db = database
        self._lock = threading.RLock()
        # Änderungszähler für zwischengespeicherte Rechte (auth/service.py):
        # steigt bei jeder Änderung an Organisationen, Konten, Mitgliedschaften
        # und Einsätzen.
        self.revision = 0

    def bump(self) -> None:
        with self._lock:
            self.revision += 1

    # -----------------------------------------------------
    # Organisationen
    # -----------------------------------------------------

    def organizations(self, *, include_archived: bool = True) -> list[dict]:
        query = select(organizations).order_by(organizations.c.name)
        if not include_archived:
            query = query.where(organizations.c.archived.is_(False))
        with self.db.engine.connect() as connection:
            return [dict(row._mapping) for row in connection.execute(query)]

    def organization(self, organization_id: int) -> dict | None:
        with self.db.engine.connect() as connection:
            row = connection.execute(
                select(organizations).where(organizations.c.id == organization_id)
            ).first()
        return dict(row._mapping) if row else None

    def _children_map(self) -> dict[int | None, list[int]]:
        children: dict[int | None, list[int]] = {}
        for org in self.organizations():
            children.setdefault(org["parent_id"], []).append(org["id"])
        return children

    def descendants(self, organization_ids) -> set[int]:
        """Organisationen samt allen darunter liegenden."""

        children = self._children_map()
        result: set[int] = set()
        stack = list(organization_ids)
        while stack:
            current = stack.pop()
            if current in result:
                continue
            result.add(current)
            stack.extend(children.get(current, []))
        return result

    def ancestors(self, organization_id: int) -> list[int]:
        parents = {org["id"]: org["parent_id"] for org in self.organizations()}
        chain = []
        current = parents.get(organization_id)
        while current is not None and current not in chain:
            chain.append(current)
            current = parents.get(current)
        return chain

    def root_ids(self) -> set[int]:
        return {org["id"] for org in self.organizations() if org["parent_id"] is None}

    def ensure_base(self) -> tuple[int, int]:
        """Landkreis und Start-Organisation anlegen, falls noch keine da sind."""

        with self._lock:
            existing = self.organizations()
            if not existing:
                root = self.create_organization(
                    name=DEFAULT_ROOT_NAME,
                    kind="landkreis",
                    parent_id=None,
                    actor="System",
                    allow_root=True,
                )
                start = self.create_organization(
                    name=DEFAULT_START_NAME,
                    kind="ortsfeuerwehr",
                    parent_id=root["id"],
                    actor="System",
                )
                return root["id"], start["id"]
            return min(self.root_ids()), self.default_organization_id()

    def default_organization_id(self) -> int:
        """Erste Wehr unterhalb der Wurzel (Start-Organisation)."""

        candidates = [
            org["id"]
            for org in self.organizations()
            if org["parent_id"] is not None and not org["archived"]
        ]
        if candidates:
            return min(candidates)
        roots = self.root_ids()
        if not roots:
            raise OrgError("Es ist noch keine Organisation angelegt.")
        return min(roots)

    def create_organization(
        self,
        *,
        name: str,
        kind: str,
        parent_id: int | None,
        short_name: str = "",
        latitude: float | None = None,
        longitude: float | None = None,
        actor: str = "",
        allow_root: bool = False,
    ) -> dict:
        name = name.strip()
        if not 2 <= len(name) <= 120:
            raise OrgError("Der Name muss 2 bis 120 Zeichen lang sein.")
        if kind not in ORGANIZATION_KINDS:
            raise OrgError("Unbekannte Art der Organisation.")
        if parent_id is None and not allow_root:
            raise OrgError("Bitte eine übergeordnete Organisation wählen.")
        if parent_id is not None and self.organization(parent_id) is None:
            raise OrgError("Die übergeordnete Organisation gibt es nicht.")
        values = {
            "name": name,
            "short_name": short_name.strip()[:40],
            "kind": kind,
            "parent_id": parent_id,
            "latitude": latitude,
            "longitude": longitude,
            "archived": False,
            "created_at": now_iso(),
        }
        with self.db.engine.begin() as connection:
            new_id = connection.execute(insert(organizations).values(**values)).inserted_primary_key[0]
        self.audit(actor, "Organisation angelegt", name, new_id)
        return {"id": new_id, **values}

    def update_organization(self, organization_id: int, *, actor: str = "", **changes) -> dict:
        current = self.organization(organization_id)
        if current is None:
            raise OrgError("Organisation nicht gefunden.")
        allowed = {"name", "short_name", "kind", "parent_id", "latitude", "longitude", "archived"}
        values = {key: value for key, value in changes.items() if key in allowed}
        if "name" in values:
            values["name"] = str(values["name"]).strip()
            if not 2 <= len(values["name"]) <= 120:
                raise OrgError("Der Name muss 2 bis 120 Zeichen lang sein.")
        if "kind" in values and values["kind"] not in ORGANIZATION_KINDS:
            raise OrgError("Unbekannte Art der Organisation.")
        if "parent_id" in values and values["parent_id"] != current["parent_id"]:
            parent = values["parent_id"]
            if current["parent_id"] is None:
                raise OrgError("Die oberste Organisation lässt sich nicht verschieben.")
            if parent is None or self.organization(parent) is None:
                raise OrgError("Die übergeordnete Organisation gibt es nicht.")
            if parent in self.descendants([organization_id]):
                raise OrgError("Eine Organisation kann nicht unter sich selbst liegen.")
        if not values:
            return current
        with self.db.engine.begin() as connection:
            connection.execute(
                update(organizations)
                .where(organizations.c.id == organization_id)
                .values(**values)
            )
        self.audit(actor, "Organisation geändert", current["name"], organization_id)
        return self.organization(organization_id)

    def delete_organization(self, organization_id: int, *, actor: str = "") -> None:
        current = self.organization(organization_id)
        if current is None:
            raise OrgError("Organisation nicht gefunden.")
        if current["parent_id"] is None:
            raise OrgError("Die oberste Organisation lässt sich nicht löschen.")
        with self.db.engine.connect() as connection:
            has_children = connection.execute(
                select(func.count()).select_from(organizations).where(
                    organizations.c.parent_id == organization_id
                )
            ).scalar_one()
            has_members = connection.execute(
                select(func.count()).select_from(memberships).where(
                    memberships.c.organization_id == organization_id
                )
            ).scalar_one()
        if has_children or has_members:
            raise OrgError(
                "Nur leere Organisationen ohne Untereinheiten und Mitglieder "
                "lassen sich löschen. Sonst bitte archivieren."
            )
        try:
            with self.db.engine.begin() as connection:
                connection.execute(
                    delete(organizations).where(organizations.c.id == organization_id)
                )
        except IntegrityError as exc:
            # z. B. Einsätze, die diese Wehr geführt hat oder an denen sie beteiligt war.
            raise OrgError(
                "Diese Organisation kommt in Einsätzen vor und bleibt für die "
                "Dokumentation erhalten. Bitte archivieren."
            ) from exc
        self.audit(actor, "Organisation gelöscht", current["name"], current["parent_id"])

    # -----------------------------------------------------
    # Konten
    # -----------------------------------------------------

    def user_count(self) -> int:
        with self.db.engine.connect() as connection:
            return connection.execute(select(func.count()).select_from(users)).scalar_one()

    def users(self) -> list[dict]:
        with self.db.engine.connect() as connection:
            rows = connection.execute(select(users).order_by(users.c.username)).all()
        return [dict(row._mapping) for row in rows]

    def user_by_username(self, username: str) -> dict | None:
        with self.db.engine.connect() as connection:
            row = connection.execute(
                select(users).where(users.c.username == username)
            ).first()
        return dict(row._mapping) if row else None

    def user_by_id(self, user_id: int) -> dict | None:
        with self.db.engine.connect() as connection:
            row = connection.execute(select(users).where(users.c.id == user_id)).first()
        return dict(row._mapping) if row else None

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        display_name: str = "",
        email: str = "",
        platform_admin: bool = False,
        actor: str = "",
        first_name: str = "",
        last_name: str = "",
        nickname: str = "",
    ) -> dict:
        if self.user_by_username(username) is not None:
            raise OrgError("Dieser Benutzername ist bereits vergeben.")
        first_name = clean_name(first_name, NAME_LIMITS["first_name"])
        last_name = clean_name(last_name, NAME_LIMITS["last_name"])
        values = {
            "username": username,
            "display_name": compose_display_name(first_name, last_name, display_name),
            "first_name": first_name,
            "last_name": last_name,
            "nickname": clean_name(nickname, NAME_LIMITS["nickname"]),
            "email": email.strip()[:254],
            "password_hash": password_hash,
            "platform_admin": platform_admin,
            "active": True,
            "created_at": now_iso(),
        }
        with self.db.engine.begin() as connection:
            new_id = connection.execute(insert(users).values(**values)).inserted_primary_key[0]
        self.audit(actor, "Konto angelegt", username)
        return {"id": new_id, **values}

    def update_user(self, user_id: int, *, actor: str = "", **changes) -> dict:
        current = self.user_by_id(user_id)
        if current is None:
            raise OrgError("Konto nicht gefunden.")
        allowed = {
            "display_name", "email", "password_hash", "platform_admin", "active",
            "last_login_at", "first_name", "last_name", "nickname",
        }
        values = {key: value for key, value in changes.items() if key in allowed}
        for key, limit in NAME_LIMITS.items():
            if key in values:
                values[key] = clean_name(values[key], limit)
        if "first_name" in values or "last_name" in values:
            # Anzeigename folgt dem Namen (Einsätze, Berichte, Protokolle).
            values["display_name"] = compose_display_name(
                values.get("first_name", current.get("first_name", "")),
                values.get("last_name", current.get("last_name", "")),
                values.get("display_name", current.get("display_name", "")),
            )
        if values.get("platform_admin") is False or values.get("active") is False:
            self._ensure_other_platform_admin(user_id)
        if values:
            with self.db.engine.begin() as connection:
                connection.execute(update(users).where(users.c.id == user_id).values(**values))
            if set(values) - {"last_login_at"}:
                self.audit(actor, "Konto geändert", current["username"])
        return self.user_by_id(user_id)

    def _ensure_other_platform_admin(self, user_id: int) -> None:
        current = self.user_by_id(user_id)
        if not current or not current["platform_admin"]:
            return
        others = [
            user for user in self.users()
            if user["platform_admin"] and user["active"] and user["id"] != user_id
        ]
        if not others:
            raise OrgError("Mindestens ein Superadmin muss erhalten bleiben.")

    def delete_user(self, user_id: int, *, actor: str = "") -> None:
        current = self.user_by_id(user_id)
        if current is None:
            raise OrgError("Konto nicht gefunden.")
        self._ensure_other_platform_admin(user_id)
        with self.db.engine.begin() as connection:
            connection.execute(delete(users).where(users.c.id == user_id))
        self.audit(actor, "Konto gelöscht", current["username"])

    # -----------------------------------------------------
    # Mitgliedschaften
    # -----------------------------------------------------

    def memberships(self, user_id: int | None = None) -> list[dict]:
        query = select(memberships)
        if user_id is not None:
            query = query.where(memberships.c.user_id == user_id)
        with self.db.engine.connect() as connection:
            return [dict(row._mapping) for row in connection.execute(query)]

    def set_membership(self, user_id: int, organization_id: int, role: str, *, actor: str = "") -> None:
        if role not in MEMBERSHIP_ROLES:
            raise OrgError("Unbekannte Rolle.")
        user = self.user_by_id(user_id)
        org = self.organization(organization_id)
        if user is None or org is None:
            raise OrgError("Konto oder Organisation nicht gefunden.")
        with self.db.engine.begin() as connection:
            existing = connection.execute(
                select(memberships.c.id).where(
                    memberships.c.user_id == user_id,
                    memberships.c.organization_id == organization_id,
                )
            ).first()
            if existing:
                connection.execute(
                    update(memberships).where(memberships.c.id == existing[0]).values(role=role)
                )
            else:
                connection.execute(
                    insert(memberships).values(
                        user_id=user_id,
                        organization_id=organization_id,
                        role=role,
                    )
                )
        self.audit(
            actor,
            f"Rolle {MEMBERSHIP_ROLES[role]} vergeben",
            f"{user['username']} · {org['name']}",
            organization_id,
        )

    def remove_membership(self, user_id: int, organization_id: int, *, actor: str = "") -> None:
        user = self.user_by_id(user_id)
        org = self.organization(organization_id)
        with self.db.engine.begin() as connection:
            connection.execute(
                delete(memberships).where(
                    memberships.c.user_id == user_id,
                    memberships.c.organization_id == organization_id,
                )
            )
        if user and org:
            self.audit(actor, "Mitgliedschaft entfernt", f"{user['username']} · {org['name']}", organization_id)

    # -----------------------------------------------------
    # Fernpilotennachweise
    # -----------------------------------------------------

    def qualifications(self, user_id: int | None = None) -> list[dict]:
        query = select(qualifications).order_by(qualifications.c.kind)
        if user_id is not None:
            query = query.where(qualifications.c.user_id == user_id)
        with self.db.engine.connect() as connection:
            rows = connection.execute(query).all()
        result = []
        today = date.today()
        for row in rows:
            item = dict(row._mapping)
            valid_until = item["valid_until"]
            item["valid"] = valid_until is None or valid_until >= today
            item["valid_until"] = valid_until.isoformat() if valid_until else None
            item["label"] = QUALIFICATION_KINDS.get(item["kind"], item["kind"])
            result.append(item)
        return result

    def add_qualification(
        self,
        user_id: int,
        *,
        kind: str,
        reference: str = "",
        valid_until: date | None = None,
        note: str = "",
        actor: str = "",
    ) -> dict:
        if kind not in QUALIFICATION_KINDS:
            raise OrgError("Unbekannte Art des Nachweises.")
        user = self.user_by_id(user_id)
        if user is None:
            raise OrgError("Konto nicht gefunden.")
        values = {
            "user_id": user_id,
            "kind": kind,
            "reference": reference.strip()[:80],
            "valid_until": valid_until,
            "note": note.strip()[:200],
        }
        with self.db.engine.begin() as connection:
            new_id = connection.execute(insert(qualifications).values(**values)).inserted_primary_key[0]
        self.audit(actor, "Nachweis erfasst", f"{user['username']} · {QUALIFICATION_KINDS[kind]}")
        return next(item for item in self.qualifications(user_id) if item["id"] == new_id)

    def qualification(self, qualification_id: int) -> dict | None:
        with self.db.engine.connect() as connection:
            row = connection.execute(
                select(qualifications).where(qualifications.c.id == qualification_id)
            ).first()
        return dict(row._mapping) if row else None

    def delete_qualification(self, qualification_id: int, *, actor: str = "") -> None:
        item = self.qualification(qualification_id)
        if item is None:
            raise OrgError("Nachweis nicht gefunden.")
        with self.db.engine.begin() as connection:
            connection.execute(delete(qualifications).where(qualifications.c.id == qualification_id))
        user = self.user_by_id(item["user_id"])
        self.audit(actor, "Nachweis gelöscht", user["username"] if user else "")

    # -----------------------------------------------------
    # Rechte
    # -----------------------------------------------------

    def scope(self, user: dict) -> Scope:
        """Organisationen, in denen ein Konto sieht, bedient, verwaltet."""

        scope = Scope(platform_admin=bool(user.get("platform_admin")))
        own = self.memberships(user["id"])
        roots = self.root_ids()
        for minimum, target in (
            ("viewer", scope.view),
            ("operator", scope.operate),
            ("admin", scope.admin),
        ):
            direct = [
                item["organization_id"]
                for item in own
                if role_at_least(item["role"], minimum)
            ]
            target.update(self.descendants(direct))
        scope.server_admin = scope.platform_admin or any(
            item["organization_id"] in roots and item["role"] == "admin"
            for item in own
        )
        if scope.platform_admin:
            everything = {org["id"] for org in self.organizations()}
            scope.view |= everything
            scope.operate |= everything
            scope.admin |= everything
        return scope

    def effective_role(self, user: dict) -> str:
        """Grobe Rolle für Seiten und Schnittstellen (höchste Rolle)."""

        if user.get("platform_admin"):
            return "superadmin"
        roles = [item["role"] for item in self.memberships(user["id"])]
        if not roles:
            return "viewer"
        return max(roles, key=ROLE_ORDER.index)

    # -----------------------------------------------------
    # Änderungsprotokoll
    # -----------------------------------------------------

    def audit(
        self,
        actor: str,
        action: str,
        target: str = "",
        organization_id: int | None = None,
    ) -> None:
        with self.db.engine.begin() as connection:
            connection.execute(
                insert(audit_log).values(
                    at=now_iso(),
                    actor=(actor or "")[:80],
                    action=action[:60],
                    target=(target or "")[:200],
                    organization_id=organization_id,
                )
            )
        self.bump()

    def audit_entries(self, organization_ids: set[int] | None = None, limit: int = 200) -> list[dict]:
        query = select(audit_log).order_by(audit_log.c.id.desc()).limit(limit)
        if organization_ids is not None:
            query = query.where(audit_log.c.organization_id.in_(organization_ids))
        with self.db.engine.connect() as connection:
            return [dict(row._mapping) for row in connection.execute(query)]
