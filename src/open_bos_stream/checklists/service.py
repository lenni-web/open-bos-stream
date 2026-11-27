"""Checklisten: wiederverwendbare Checklisten und ihre Durchführungen.

Eine wiederverwendbare Checkliste heißt intern „Vorlage“ (Tabelle
checklist_templates), eine Durchführung ist ein Eintrag in checklists.

* Vorlagen der obersten Organisation (Landkreis) gelten für alle; sie pflegen
  nur Drohnenteams und Admins auf Landkreisebene.
* Jede Wehr pflegt zusätzlich eigene Vorlagen, die nur sie selbst sieht.
* Listen in einem Einsatz folgen den Rechten des Einsatzes: Nach dem
  Abschluss des Einsatzes ändern sie nur noch Admins der führenden Wehr.
* Eigene Listen ohne Einsatz lassen sich abschließen; danach ändern sie nur
  noch Admins der Wehr.
"""

from __future__ import annotations

import json
import threading

from sqlalchemy import delete, func, insert, select, update

from open_bos_stream.db.schema import (
    CHECKLIST_STATUS,
    checklist_items,
    checklist_templates,
    checklists,
)
from open_bos_stream.incidents.service import (
    IncidentAccessError,
    IncidentError,
    IncidentService,
    iso,
    local_now,
)

MAX_ITEMS = 200


class ChecklistError(IncidentError):
    """Ungültige Angaben zu einer Checkliste."""


class ChecklistAccessError(IncidentAccessError):
    """Keine Berechtigung für diese Checkliste oder Vorlage."""


def _actor(user: dict) -> str:
    return user.get("display_name") or user["username"]


def _unrestricted(user: dict) -> bool:
    if user.get("role") == "guest":
        return False
    return bool(user.get("platform_admin")) or "org_view" not in user


def _text(value, limit: int, field: str, *, required: bool = False) -> str:
    text = " ".join(str(value or "").split())
    if required and not text:
        raise ChecklistError(f"{field} fehlt.")
    if len(text) > limit:
        raise ChecklistError(f"{field} ist zu lang (max. {limit} Zeichen).")
    return text


def clean_items(items) -> list[dict]:
    """Positionen prüfen: Text, Abschnitt, Hinweis, Pflicht."""

    if not isinstance(items, list):
        raise ChecklistError("Positionen fehlen.")
    if len(items) > MAX_ITEMS:
        raise ChecklistError(f"Höchstens {MAX_ITEMS} Positionen je Liste.")
    result = []
    for item in items:
        if not isinstance(item, dict):
            raise ChecklistError("Ungültige Position.")
        text = _text(item.get("text"), 300, "Text einer Position")
        if not text:
            continue
        result.append({
            "section": _text(item.get("section"), 80, "Abschnitt"),
            "text": text,
            "hint": _text(item.get("hint"), 300, "Hinweis"),
            "required": bool(item.get("required")),
        })
    return result


class ChecklistService:
    def __init__(self, incidents: IncidentService) -> None:
        self.incidents = incidents
        self._lock = threading.RLock()

    @property
    def org(self):
        return self.incidents.org

    @property
    def _engine(self):
        return self.org.db.engine

    # -----------------------------------------------------
    # Rechte
    # -----------------------------------------------------

    def can_manage_templates(self, user: dict | None) -> bool:
        """Drohnenteam oder Admin auf Landkreisebene (oberste Organisation)."""

        if not user or user.get("role") == "guest":
            return False
        if _unrestricted(user):
            return True
        return bool(set(user.get("org_operate") or []) & self.org.root_ids())

    def can_view_template(self, user: dict | None, template: dict) -> bool:
        if not user or user.get("role") == "guest":
            return False
        owner = template["organization_id"]
        return (
            _unrestricted(user)
            or owner in self.org.root_ids()
            or owner in set(user.get("org_view") or [])
            or self.can_manage_template(user, owner)
        )

    def can_manage_template(self, user: dict | None, organization_id: int) -> bool:
        """Landkreis-Vorlagen: Landkreisebene; Wehr-Vorlagen: Team/Admin der Wehr."""

        if not user or user.get("role") == "guest":
            return False
        if organization_id in self.org.root_ids():
            return self.can_manage_templates(user)
        if _unrestricted(user):
            return True
        return organization_id in set(user.get("org_operate") or []) | set(user.get("org_admin") or [])

    def template_owners(self, user: dict) -> list[int]:
        """Organisationen, für die dieses Konto Vorlagen anlegen darf (Landkreis zuerst)."""

        roots = self.org.root_ids()
        result = [self.template_owner(user)] if self.can_manage_templates(user) else []
        return result + [item for item in self.lead_options(user) if item not in roots]

    def template_owner(self, user: dict) -> int:
        roots = sorted(self.org.root_ids())
        own = [item for item in roots if item in set(user.get("org_operate") or [])]
        if own:
            return own[0]
        if roots:
            return roots[0]
        raise ChecklistError("Keine oberste Organisation vorhanden.")

    def lead_options(self, user: dict) -> list[int]:
        """Wehren, für die dieses Konto eigene Listen anlegen darf."""

        if _unrestricted(user):
            return [item["id"] for item in self.org.organizations(include_archived=False)]
        return sorted(set(user.get("org_operate") or []))

    def access(self, user: dict | None, checklist: dict) -> dict:
        """{"view", "edit", "admin"} für eine Liste."""

        none = {"view": False, "edit": False, "admin": False}
        if not user or user.get("role") == "guest":
            return none
        if checklist.get("incident_id"):
            incident = self.incidents.get(checklist["incident_id"])
            if incident is None or not self.incidents.can_view(user, incident):
                return none
            return {
                "view": True,
                "edit": self.incidents.can_edit(user, incident),
                "admin": self.incidents.can_administer(user, incident),
            }
        if _unrestricted(user):
            return {"view": True, "edit": True, "admin": True}
        organization = checklist["organization_id"]
        view = organization in set(user.get("org_view") or [])
        operate = organization in set(user.get("org_operate") or [])
        admin = organization in set(user.get("org_admin") or []) or bool(user.get("server_admin"))
        if not view and not admin:
            return none
        edit = admin if checklist["status"] == "completed" else (operate or admin)
        return {"view": True, "edit": edit, "admin": admin}

    # -----------------------------------------------------
    # Vorlagen
    # -----------------------------------------------------

    @staticmethod
    def _template_row(row) -> dict:
        item = dict(row._mapping)
        try:
            item["items"] = json.loads(item["items"] or "[]")
        except ValueError:
            item["items"] = []
        item["item_count"] = len(item["items"])
        item["required_count"] = sum(1 for entry in item["items"] if entry.get("required"))
        return item

    def templates(self, *, include_archived: bool = False) -> list[dict]:
        query = select(checklist_templates).order_by(checklist_templates.c.title)
        if not include_archived:
            query = query.where(checklist_templates.c.archived.is_(False))
        with self._engine.connect() as connection:
            return [self._template_row(row) for row in connection.execute(query)]

    def template(self, template_id: int) -> dict | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                select(checklist_templates).where(checklist_templates.c.id == template_id)
            ).first()
        return self._template_row(row) if row else None

    def visible_templates(self, user: dict, *, include_archived: bool = False) -> list[dict]:
        """Vorlagen, die dieses Konto sieht; archivierte nur, wenn es sie pflegt."""

        result = []
        for item in self.templates(include_archived=include_archived):
            if not self.can_view_template(user, item):
                continue
            manage = self.can_manage_template(user, item["organization_id"])
            if item["archived"] and not manage:
                continue
            result.append(item | {"can_manage": manage})
        return result

    def require_template(self, user: dict, template_id: int, *, manage: bool = False) -> dict:
        template = self.template(template_id)
        if template is None or not self.can_view_template(user, template):
            raise LookupError("Checkliste nicht gefunden.")
        if manage and not self.can_manage_template(user, template["organization_id"]):
            raise ChecklistAccessError(
                "Landkreis-Checklisten pflegt der Landkreis, eigene das Drohnenteam der Wehr."
            )
        return template

    def create_template(
        self, user: dict, *, title: str, description: str = "", items=None,
        organization_id: int | None = None,
    ) -> dict:
        """Ohne organization_id: Checkliste des Landkreises."""

        if organization_id is None:
            organization_id = self.template_owner(user)
        known = {item["id"] for item in self.org.organizations(include_archived=False)}
        if organization_id not in known or not self.can_manage_template(user, organization_id):
            raise ChecklistAccessError(
                "Landkreis-Checklisten pflegt der Landkreis, eigene das Drohnenteam der Wehr."
            )
        values = {
            "title": _text(title, 120, "Titel", required=True),
            "description": str(description or "").strip()[:2000],
            "items": json.dumps(clean_items(items or []), ensure_ascii=False),
        }
        now = iso(local_now())
        with self._engine.begin() as connection:
            template_id = connection.execute(
                insert(checklist_templates).values(
                    organization_id=organization_id,
                    version=1,
                    archived=False,
                    created_by=_actor(user),
                    created_at=now,
                    updated_by=_actor(user),
                    updated_at=now,
                    **values,
                )
            ).inserted_primary_key[0]
        self.org.audit(_actor(user), "Checklisten-Vorlage angelegt", values["title"])
        return self.template(template_id)

    def update_template(self, user: dict, template_id: int, **changes) -> dict:
        current = self.require_template(user, template_id, manage=True)
        values = {}
        if changes.get("title") is not None:
            values["title"] = _text(changes["title"], 120, "Titel", required=True)
        if changes.get("description") is not None:
            values["description"] = str(changes["description"]).strip()[:2000]
        if changes.get("items") is not None:
            values["items"] = json.dumps(clean_items(changes["items"]), ensure_ascii=False)
        if changes.get("archived") is not None:
            values["archived"] = bool(changes["archived"])
        if not values:
            return current
        if "items" in values or "title" in values:
            # Bereits angelegte Listen behalten ihren Stand; neue nutzen die neue Version.
            values["version"] = current["version"] + 1
        values.update(updated_by=_actor(user), updated_at=iso(local_now()))
        with self._engine.begin() as connection:
            connection.execute(
                update(checklist_templates)
                .where(checklist_templates.c.id == template_id)
                .values(**values)
            )
        self.org.audit(_actor(user), "Checklisten-Vorlage geändert", values.get("title", current["title"]))
        return self.template(template_id)

    def delete_template(self, user: dict, template_id: int) -> None:
        current = self.require_template(user, template_id, manage=True)
        with self._engine.begin() as connection:
            connection.execute(delete(checklist_templates).where(checklist_templates.c.id == template_id))
        self.org.audit(_actor(user), "Checklisten-Vorlage gelöscht", current["title"])

    # -----------------------------------------------------
    # Listen
    # -----------------------------------------------------

    def _items(self, connection, checklist_ids: list[int]) -> dict[int, list[dict]]:
        result: dict[int, list[dict]] = {item: [] for item in checklist_ids}
        if not checklist_ids:
            return result
        rows = connection.execute(
            select(checklist_items)
            .where(checklist_items.c.checklist_id.in_(checklist_ids))
            .order_by(checklist_items.c.position, checklist_items.c.id)
        ).all()
        for row in rows:
            result[row.checklist_id].append(dict(row._mapping))
        return result

    @staticmethod
    def _progress(item: dict, items: list[dict]) -> dict:
        item["total"] = len(items)
        item["done"] = sum(1 for entry in items if entry["checked"])
        item["open_required"] = [entry["text"] for entry in items if entry["required"] and not entry["checked"]]
        item["status_label"] = CHECKLIST_STATUS.get(item["status"], item["status"])
        return item

    def _load(self, query) -> list[dict]:
        with self._engine.connect() as connection:
            rows = [dict(row._mapping) for row in connection.execute(query)]
            items = self._items(connection, [row["id"] for row in rows])
        return [self._progress(row, items[row["id"]]) | {"items": items[row["id"]]} for row in rows]

    def get(self, checklist_id: int) -> dict | None:
        rows = self._load(select(checklists).where(checklists.c.id == checklist_id))
        return rows[0] if rows else None

    def require(self, user: dict, checklist_id: int, *, edit: bool = False) -> dict:
        checklist = self.get(checklist_id)
        rights = self.access(user, checklist) if checklist else {"view": False}
        if not checklist or not rights["view"]:
            raise LookupError("Checkliste nicht gefunden.")
        if edit and not rights["edit"]:
            raise ChecklistAccessError(
                "Diese Checkliste ist abgeschlossen; Änderungen nur noch durch Admins "
                + ("der führenden Wehr." if checklist.get("incident_id") else "der Wehr.")
            )
        return checklist | {"can": rights}

    def visible(self, user: dict) -> list[dict]:
        rows = self._load(select(checklists).order_by(checklists.c.created_at.desc()))
        result = []
        incidents_cache: dict[int, dict | None] = {}
        for row in rows:
            rights = self.access(user, row)
            if not rights["view"]:
                continue
            row.pop("items", None)
            if row["incident_id"]:
                incident = incidents_cache.setdefault(row["incident_id"], self.incidents.get(row["incident_id"]))
                row["incident"] = (
                    {key: incident[key] for key in ("id", "code", "keyword", "status", "exercise")}
                    if incident else None
                )
            result.append(row | {"can": rights})
        return result

    def for_incident(self, incident_id: int) -> list[dict]:
        return self._load(
            select(checklists)
            .where(checklists.c.incident_id == incident_id)
            .order_by(checklists.c.created_at)
        )

    def create(
        self,
        user: dict,
        *,
        title: str = "",
        description: str = "",
        template_id: int | None = None,
        incident_id: int | None = None,
        organization_id: int | None = None,
        items=None,
    ) -> dict:
        template = None
        if template_id is not None:
            template = self.template(template_id)
            if template is None or template["archived"] or not self.can_view_template(user, template):
                raise ChecklistError("Vorlage nicht gefunden.")
        if incident_id is not None:
            incident = self.incidents.require(user, incident_id, edit=True)
            organization_id = incident["lead_organization_id"]
        else:
            incident = None
            if organization_id is None or organization_id not in self.lead_options(user):
                raise ChecklistAccessError("Eigene Listen legt das Drohnenteam der Wehr an.")
        entries = clean_items(template["items"] if template else (items or []))
        title = _text(title or (template["title"] if template else ""), 120, "Titel", required=True)
        now = iso(local_now())
        actor = _actor(user)
        with self._lock, self._engine.begin() as connection:
            checklist_id = connection.execute(
                insert(checklists).values(
                    title=title,
                    description=str(description or (template["description"] if template else "")).strip()[:2000],
                    template_id=template["id"] if template else None,
                    template_version=template["version"] if template else None,
                    organization_id=organization_id,
                    incident_id=incident_id,
                    status="open",
                    created_by=actor,
                    created_at=now,
                )
            ).inserted_primary_key[0]
            for position, entry in enumerate(entries):
                connection.execute(insert(checklist_items).values(
                    checklist_id=checklist_id, position=position, **entry,
                ))
            if incident is not None:
                self.incidents._log(connection, incident_id, actor, "checklist", f"Checkliste „{title}“ hinzugefügt")
        return self.require(user, checklist_id)

    def update(self, user: dict, checklist_id: int, **changes) -> dict:
        current = self.require(user, checklist_id, edit=True)
        values = {}
        if changes.get("title") is not None:
            values["title"] = _text(changes["title"], 120, "Titel", required=True)
        if changes.get("description") is not None:
            values["description"] = str(changes["description"]).strip()[:2000]
        if values:
            with self._engine.begin() as connection:
                connection.execute(update(checklists).where(checklists.c.id == checklist_id).values(**values))
        return self.require(user, current["id"])

    def set_item(self, user: dict, checklist_id: int, item_id: int, *, checked=None, note=None) -> dict:
        checklist = self.require(user, checklist_id, edit=True)
        item = next((entry for entry in checklist["items"] if entry["id"] == item_id), None)
        if item is None:
            raise LookupError("Position nicht gefunden.")
        now = iso(local_now())
        actor = _actor(user)
        values = {}
        if checked is not None and bool(checked) != item["checked"]:
            values.update(
                checked=bool(checked),
                checked_by=actor if checked else None,
                checked_at=now if checked else None,
            )
        if note is not None:
            text = str(note).strip()
            if len(text) > 1000:
                raise ChecklistError("Die Anmerkung ist zu lang (max. 1000 Zeichen).")
            if text != item["note"]:
                values.update(note=text, note_by=actor if text else None, note_at=now if text else None)
        if values:
            with self._engine.begin() as connection:
                connection.execute(update(checklist_items).where(checklist_items.c.id == item_id).values(**values))
        return self.require(user, checklist_id)

    def add_item(self, user: dict, checklist_id: int, *, text: str, section: str = "", hint: str = "", required: bool = False) -> dict:
        checklist = self.require(user, checklist_id, edit=True)
        if len(checklist["items"]) >= MAX_ITEMS:
            raise ChecklistError(f"Höchstens {MAX_ITEMS} Positionen je Liste.")
        entry = clean_items([{"text": text, "section": section, "hint": hint, "required": required}])
        if not entry:
            raise ChecklistError("Bitte einen Text für die Position eingeben.")
        with self._engine.begin() as connection:
            position = connection.execute(
                select(func.coalesce(func.max(checklist_items.c.position), -1)).where(
                    checklist_items.c.checklist_id == checklist_id
                )
            ).scalar_one() + 1
            connection.execute(insert(checklist_items).values(
                checklist_id=checklist_id, position=position, **entry[0],
            ))
        return self.require(user, checklist_id)

    def remove_item(self, user: dict, checklist_id: int, item_id: int) -> dict:
        checklist = self.require(user, checklist_id, edit=True)
        if not any(entry["id"] == item_id for entry in checklist["items"]):
            raise LookupError("Position nicht gefunden.")
        with self._engine.begin() as connection:
            connection.execute(delete(checklist_items).where(checklist_items.c.id == item_id))
        return self.require(user, checklist_id)

    def set_status(self, user: dict, checklist_id: int, status: str) -> dict:
        if status not in CHECKLIST_STATUS:
            raise ChecklistError("Unbekannter Status.")
        checklist = self.require(user, checklist_id)
        if checklist["incident_id"]:
            raise ChecklistError("Einsatz-Checklisten werden mit dem Einsatz abgeschlossen.")
        if status == checklist["status"]:
            return checklist
        if status == "completed" and not checklist["can"]["edit"]:
            raise ChecklistAccessError("Keine Berechtigung für diese Checkliste.")
        if status == "open" and not checklist["can"]["admin"]:
            raise ChecklistAccessError("Wieder öffnen dürfen nur Admins der Wehr.")
        values = (
            {"status": "completed", "completed_by": _actor(user), "completed_at": iso(local_now())}
            if status == "completed"
            else {"status": "open", "completed_by": None, "completed_at": None}
        )
        with self._engine.begin() as connection:
            connection.execute(update(checklists).where(checklists.c.id == checklist_id).values(**values))
        return self.require(user, checklist_id)

    def delete(self, user: dict, checklist_id: int) -> None:
        checklist = self.require(user, checklist_id, edit=True)
        with self._lock, self._engine.begin() as connection:
            connection.execute(delete(checklists).where(checklists.c.id == checklist_id))
            if checklist["incident_id"]:
                self.incidents._log(
                    connection, checklist["incident_id"], _actor(user), "checklist",
                    f"Checkliste „{checklist['title']}“ entfernt",
                )
