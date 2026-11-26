"""Verwaltung von Organisationen, Konten, Rollen und Fernpilotennachweisen.

Rechte:
* Organisationen sehen alle Angemeldeten (Namen für Auswahllisten).
* Anlegen, Ändern, Löschen: Admin der übergeordneten Organisation
  (Kreis-Admin für alles im Landkreis), die oberste nur der Superadmin.
* Konten: Admins verwalten Konten, deren Mitgliedschaften vollständig in
  ihrem Bereich liegen. Rollen vergeben sie nur in ihrem Bereich.
* Superadmin-Konten verwaltet nur ein Superadmin.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from open_bos_stream.auth.roles import ADMIN, VIEWER
from open_bos_stream.auth.service import AuthError
from open_bos_stream.core.container import (
    auth_service,
    config as runtime_config,
    server_event_log,
)
from open_bos_stream.db.schema import (
    MEMBERSHIP_ROLES,
    ORGANIZATION_KINDS,
    QUALIFICATION_KINDS,
)
from open_bos_stream.org.service import OrgError


router = APIRouter(prefix="/api/org", tags=["organisation"])


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    short_name: str = Field(default="", max_length=40)
    kind: str
    parent_id: int | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    short_name: str | None = Field(default=None, max_length=40)
    kind: str | None = None
    parent_id: int | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    archived: bool | None = None


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=10, max_length=1024)
    display_name: str = Field(default="", max_length=80)
    email: str = Field(default="", max_length=254)
    organization_id: int
    role: str = "viewer"


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=254)
    password: str | None = Field(default=None, min_length=10, max_length=1024)
    active: bool | None = None
    platform_admin: bool | None = None


class MembershipUpdate(BaseModel):
    role: str


class QualificationCreate(BaseModel):
    kind: str
    reference: str = Field(default="", max_length=80)
    valid_until: date | None = None
    note: str = Field(default="", max_length=200)


# ---------------------------------------------------------
# Hilfen
# ---------------------------------------------------------

def _org():
    return auth_service.ready()


def _user(request: Request) -> dict:
    return request.state.user


def _actor(request: Request) -> str:
    return _user(request).get("username", "")


def _admin_scope(request: Request) -> set[int]:
    return set(_user(request).get("org_admin") or [])


def _is_platform_admin(request: Request) -> bool:
    user = _user(request)
    return bool(user.get("platform_admin")) or user.get("role") == "superadmin"


def _require_org_admin(request: Request, organization_id: int | None) -> None:
    if _is_platform_admin(request):
        return
    if organization_id is None or organization_id not in _admin_scope(request):
        raise HTTPException(
            status_code=403,
            detail="Dafür fehlt die Rolle Wehr-Admin in dieser Organisation.",
        )


def _can_manage_account(request: Request, target: dict) -> bool:
    if _is_platform_admin(request):
        return True
    if target["platform_admin"]:
        return False
    scope = _admin_scope(request)
    own = [item["organization_id"] for item in _org().memberships(target["id"])]
    return bool(own) and all(item in scope for item in own)


def _require_account(request: Request, user_id: int) -> dict:
    target = _org().user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Konto nicht gefunden.")
    if not _can_manage_account(request, target):
        raise HTTPException(
            status_code=403,
            detail=(
                "Dieses Konto gehört auch zu Organisationen außerhalb Ihres "
                "Bereichs und wird dort verwaltet."
            ),
        )
    return target


def _org_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


def _public_user(request: Request, user: dict) -> dict:
    org = _org()
    scope = _admin_scope(request)
    platform = _is_platform_admin(request)
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "email": user["email"],
        "active": bool(user["active"]),
        "platform_admin": bool(user["platform_admin"]),
        "last_login_at": user["last_login_at"],
        "manageable": _can_manage_account(request, user),
        "memberships": [
            {
                "organization_id": item["organization_id"],
                "role": item["role"],
                "editable": platform or item["organization_id"] in scope,
            }
            for item in org.memberships(user["id"])
        ],
        "qualifications": org.qualifications(user["id"]),
    }


# ---------------------------------------------------------
# Stammdaten
# ---------------------------------------------------------

@router.get("/meta", dependencies=[VIEWER])
def meta() -> dict:
    return {
        "organization_kinds": ORGANIZATION_KINDS,
        "roles": MEMBERSHIP_ROLES,
        "qualification_kinds": QUALIFICATION_KINDS,
    }


@router.get("/organizations", dependencies=[VIEWER])
def list_organizations(request: Request) -> dict:
    org = _org()
    scope = _admin_scope(request)
    platform = _is_platform_admin(request)
    members = {}
    for item in org.memberships():
        members[item["organization_id"]] = members.get(item["organization_id"], 0) + 1
    sources = {}
    for source in runtime_config.sources:
        if source.organization_id is not None:
            sources[source.organization_id] = sources.get(source.organization_id, 0) + 1
    return {
        "organizations": [
            {
                **item,
                "kind_label": ORGANIZATION_KINDS.get(item["kind"], item["kind"]),
                "can_admin": platform or item["id"] in scope,
                "can_manage_children": platform or item["id"] in scope,
                "can_edit": platform or (
                    item["parent_id"] is not None and item["parent_id"] in scope
                ),
                "member_count": members.get(item["id"], 0),
                "source_count": sources.get(item["id"], 0),
            }
            for item in org.organizations()
        ],
    }


@router.post("/organizations", dependencies=[ADMIN])
def create_organization(payload: OrganizationCreate, request: Request) -> dict:
    if payload.parent_id is None:
        if not _is_platform_admin(request):
            raise HTTPException(
                status_code=403,
                detail="Eine oberste Organisation legt nur ein Superadmin an.",
            )
    else:
        _require_org_admin(request, payload.parent_id)
    try:
        created = _org().create_organization(
            name=payload.name,
            short_name=payload.short_name,
            kind=payload.kind,
            parent_id=payload.parent_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            actor=_actor(request),
            allow_root=payload.parent_id is None,
        )
    except OrgError as exc:
        raise _org_error(exc) from exc
    server_event_log.record(
        "info",
        f"🏢 Organisation angelegt: {created['name']}",
        actor=_actor(request),
        organization_id=created["id"],
    )
    return {"success": True, "organization": created}


@router.patch("/organizations/{organization_id}", dependencies=[ADMIN])
def update_organization(
    organization_id: int,
    payload: OrganizationUpdate,
    request: Request,
) -> dict:
    org = _org()
    current = org.organization(organization_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
    changes = payload.model_dump(exclude_unset=True)
    # Name, Kurzname und Standort darf auch der Admin der Organisation selbst
    # ändern; Art, Einordnung und Archivierung nur die Ebene darüber.
    structural = {"kind", "parent_id", "archived"} & set(changes)
    if structural:
        _require_org_admin(request, current["parent_id"])
        if "parent_id" in changes:
            _require_org_admin(request, changes["parent_id"])
    else:
        _require_org_admin(request, organization_id)
    try:
        updated = org.update_organization(
            organization_id,
            actor=_actor(request),
            **changes,
        )
    except OrgError as exc:
        raise _org_error(exc) from exc
    return {"success": True, "organization": updated}


@router.delete("/organizations/{organization_id}", dependencies=[ADMIN])
def delete_organization(organization_id: int, request: Request) -> dict:
    org = _org()
    current = org.organization(organization_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
    _require_org_admin(request, current["parent_id"])
    if any(source.organization_id == organization_id for source in runtime_config.sources):
        raise HTTPException(
            status_code=409,
            detail="Der Organisation sind noch Quellen zugeordnet.",
        )
    try:
        org.delete_organization(organization_id, actor=_actor(request))
    except OrgError as exc:
        raise _org_error(exc) from exc
    server_event_log.record(
        "info",
        f"🏢 Organisation gelöscht: {current['name']}",
        actor=_actor(request),
        organization_id=current["parent_id"],
    )
    return {"success": True}


# ---------------------------------------------------------
# Konten
# ---------------------------------------------------------

@router.get("/users", dependencies=[ADMIN])
def list_users(request: Request) -> dict:
    org = _org()
    platform = _is_platform_admin(request)
    scope = _admin_scope(request)
    visible = []
    for user in org.users():
        own = {item["organization_id"] for item in org.memberships(user["id"])}
        if platform or own & scope:
            visible.append(_public_user(request, user))
    return {"users": visible}


@router.post("/users", dependencies=[ADMIN])
def create_user(payload: UserCreate, request: Request) -> dict:
    _require_org_admin(request, payload.organization_id)
    if payload.role not in MEMBERSHIP_ROLES:
        raise HTTPException(status_code=422, detail="Unbekannte Rolle.")
    try:
        created = auth_service.create_user(
            payload.username,
            payload.password,
            payload.role,
            organization_id=payload.organization_id,
            display_name=payload.display_name,
            email=payload.email,
            actor=_actor(request),
        )
    except AuthError as exc:
        raise _org_error(exc) from exc
    server_event_log.record(
        "info",
        f"👤 Konto angelegt: {created['username']}",
        actor=_actor(request),
        organization_id=payload.organization_id,
    )
    return {
        "success": True,
        "user": _public_user(request, _org().user_by_id(created["user_id"])),
    }


@router.patch("/users/{user_id}", dependencies=[ADMIN])
def update_user(user_id: int, payload: UserUpdate, request: Request) -> dict:
    target = _require_account(request, user_id)
    changes = payload.model_dump(exclude_unset=True)
    if "platform_admin" in changes and not _is_platform_admin(request):
        raise HTTPException(
            status_code=403,
            detail="Die Superadmin-Rolle vergibt nur ein Superadmin.",
        )
    if changes.get("active") is False and target["id"] == _user(request).get("user_id"):
        raise HTTPException(status_code=409, detail="Das eigene Konto lässt sich nicht sperren.")
    password = changes.pop("password", None)
    try:
        if password:
            auth_service.set_password(user_id, password, actor=_actor(request))
        if changes:
            _org().update_user(user_id, actor=_actor(request), **changes)
    except (AuthError, OrgError) as exc:
        raise _org_error(exc) from exc
    return {"success": True, "user": _public_user(request, _org().user_by_id(user_id))}


@router.delete("/users/{user_id}", dependencies=[ADMIN])
def delete_user(user_id: int, request: Request) -> dict:
    target = _require_account(request, user_id)
    if target["id"] == _user(request).get("user_id"):
        raise HTTPException(status_code=409, detail="Das eigene Konto kann nicht gelöscht werden.")
    try:
        _org().delete_user(user_id, actor=_actor(request))
    except OrgError as exc:
        raise _org_error(exc) from exc
    server_event_log.record("info", f"👤 Konto gelöscht: {target['username']}", actor=_actor(request))
    return {"success": True}


@router.put("/users/{user_id}/memberships/{organization_id}", dependencies=[ADMIN])
def set_membership(
    user_id: int,
    organization_id: int,
    payload: MembershipUpdate,
    request: Request,
) -> dict:
    _require_org_admin(request, organization_id)
    org = _org()
    target = org.user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Konto nicht gefunden.")
    if target["platform_admin"] and not _is_platform_admin(request):
        raise HTTPException(status_code=403, detail="Superadmin-Konten verwaltet nur ein Superadmin.")
    try:
        org.set_membership(user_id, organization_id, payload.role, actor=_actor(request))
    except OrgError as exc:
        raise _org_error(exc) from exc
    return {"success": True, "user": _public_user(request, org.user_by_id(user_id))}


@router.delete("/users/{user_id}/memberships/{organization_id}", dependencies=[ADMIN])
def remove_membership(user_id: int, organization_id: int, request: Request) -> dict:
    _require_org_admin(request, organization_id)
    org = _org()
    target = org.user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Konto nicht gefunden.")
    if target["platform_admin"] and not _is_platform_admin(request):
        raise HTTPException(status_code=403, detail="Superadmin-Konten verwaltet nur ein Superadmin.")
    org.remove_membership(user_id, organization_id, actor=_actor(request))
    return {"success": True, "user": _public_user(request, org.user_by_id(user_id))}


# ---------------------------------------------------------
# Fernpilotennachweise
# ---------------------------------------------------------

def _require_qualification_access(request: Request, user_id: int) -> None:
    if user_id == _user(request).get("user_id"):
        return
    _require_account(request, user_id)


@router.post("/users/{user_id}/qualifications", dependencies=[VIEWER])
def add_qualification(
    user_id: int,
    payload: QualificationCreate,
    request: Request,
) -> dict:
    _require_qualification_access(request, user_id)
    try:
        item = _org().add_qualification(
            user_id,
            kind=payload.kind,
            reference=payload.reference,
            valid_until=payload.valid_until,
            note=payload.note,
            actor=_actor(request),
        )
    except OrgError as exc:
        raise _org_error(exc) from exc
    return {"success": True, "qualification": item}


@router.delete("/qualifications/{qualification_id}", dependencies=[VIEWER])
def delete_qualification(qualification_id: int, request: Request) -> dict:
    org = _org()
    item = org.qualification(qualification_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Nachweis nicht gefunden.")
    _require_qualification_access(request, item["user_id"])
    org.delete_qualification(qualification_id, actor=_actor(request))
    return {"success": True}


# ---------------------------------------------------------
# Eigenes Konto
# ---------------------------------------------------------

class OwnAccountUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=254)
    current_password: str | None = Field(default=None, max_length=1024)
    new_password: str | None = Field(default=None, min_length=10, max_length=1024)


@router.get("/me", dependencies=[VIEWER])
def me(request: Request) -> dict:
    org = _org()
    stored = org.user_by_id(_user(request).get("user_id") or 0)
    if stored is None:
        raise HTTPException(status_code=404, detail="Kein persönliches Konto.")
    return {
        "user": {
            "id": stored["id"],
            "username": stored["username"],
            "display_name": stored["display_name"],
            "email": stored["email"],
            "memberships": org.memberships(stored["id"]),
            "qualifications": org.qualifications(stored["id"]),
        }
    }


@router.patch("/me", dependencies=[VIEWER])
def update_me(payload: OwnAccountUpdate, request: Request) -> dict:
    org = _org()
    stored = org.user_by_id(_user(request).get("user_id") or 0)
    if stored is None:
        raise HTTPException(status_code=404, detail="Kein persönliches Konto.")
    changes = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if key in {"display_name", "email"} and value is not None
    }
    if payload.new_password:
        if not auth_service.authenticate(stored["username"], payload.current_password or ""):
            raise HTTPException(status_code=403, detail="Das bisherige Passwort ist falsch.")
        auth_service.set_password(stored["id"], payload.new_password, actor=stored["username"])
    if changes:
        org.update_user(stored["id"], actor=stored["username"], **changes)
    return {"success": True}


@router.get("/audit", dependencies=[ADMIN])
def audit(request: Request) -> dict:
    scope = None if _is_platform_admin(request) or _user(request).get("server_admin") else _admin_scope(request)
    return {"entries": _org().audit_entries(scope)}
