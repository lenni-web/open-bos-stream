"""Einsätze: anlegen, führen, dokumentieren, Bericht."""

from __future__ import annotations

import logging
import time
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from open_bos_stream.api.dji import drone_service
from open_bos_stream.api.weather import default_location, weather_service
from open_bos_stream.auth.guest_access import can_operate_source
from open_bos_stream.auth.guest_links import MAX_HOURS, GuestLinkError
from open_bos_stream.auth.roles import VIEWER
from open_bos_stream.core.container import (
    auth_service,
    config,
    guest_link_store,
    media_library,
    push_service,
    recording_library,
    server_event_log,
    snapshot_library,
)
from open_bos_stream.db.schema import INCIDENT_ROLES, INCIDENT_STATUS
from open_bos_stream.checklists.service import ChecklistService
from open_bos_stream.incidents.map import IncidentMap
from open_bos_stream.incidents.service import (
    IncidentAccessError,
    IncidentError,
    parse_time,
)
from open_bos_stream.notifications.monitor import Notice
from open_bos_stream.version import VERSION

router = APIRouter(
    dependencies=[VIEWER],
    prefix="/api/incidents",
    tags=["Einsätze"],
)
logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="src/open_bos_stream/templates")


def _service():
    auth_service.ready()
    return auth_service.incidents


def _map() -> IncidentMap:
    return IncidentMap(_service())


def _actor(user: dict) -> str:
    return user.get("display_name") or user["username"]


async def _call(function, *args, **kwargs):
    """Dienstaufruf im Thread; Fehler als passende HTTP-Antwort."""

    try:
        return await run_in_threadpool(lambda: function(*args, **kwargs))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'\"")) from exc
    except IncidentAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (IncidentError, GuestLinkError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _user(request: Request) -> dict:
    user = request.state.user
    if user.get("role") == "guest":
        raise HTTPException(status_code=403, detail="Nur für angemeldete Konten.")
    return user


def _source(source_id: str):
    return next((item for item in config.sources if item.id == source_id), None)


def _summary(incident: dict) -> dict:
    service = _service()
    return {
        key: incident[key]
        for key in (
            "id", "code", "title", "keyword", "address", "alarm_at", "ended_at",
            "status", "status_label", "lead_organization_id", "organization_ids",
            "latitude", "longitude", "exercise",
        )
    } | {
        "lead_name": service._org_name(incident["lead_organization_id"]),
        "source_count": len(service.active_source_ids(incident["id"])),
    }


def _org_names() -> dict[int, str]:
    return {
        item["id"]: item["short_name"] or item["name"]
        for item in _service().all_organizations()
    }


def _incident_media(incident: dict) -> list[dict]:
    return _service().media(incident, media_library.list())


def _detail(user: dict, incident_id: int) -> dict:
    service = _service()
    incident = service.require(user, incident_id)
    names = _org_names()
    can_edit = service.can_edit(user, incident)
    sources = []
    for entry in service.sources(incident_id):
        current = _source(entry["source_id"])
        sources.append(entry | {
            "name": current.name if current else entry["source_name"],
            "drone_type": current.drone_type if current else "",
            "exists": current is not None,
        })
    assigned = set(service.active_source_ids(incident_id))
    detail = {
        "incident": incident | {
            "lead_name": names.get(incident["lead_organization_id"], "?"),
            "involved": [
                entry | {"name": names.get(entry["organization_id"], "?")}
                for entry in incident["involved"]
            ],
        },
        "participants": service.participants(incident_id),
        "sources": sources,
        "log": service.log(incident_id),
        "checklists": [
            {
                key: item[key]
                for key in ("id", "title", "total", "done", "open_required", "items", "template_id")
            }
            for item in ChecklistService(service).for_incident(incident_id)
        ],
        "map_items": [
            {key: item[key] for key in ("id", "name", "status", "status_label", "assignee", "note", "updated_at", "updated_by")}
            for item in _map().items(incident_id)
        ],
        "media": _incident_media(incident),
        "telemetry": drone_service().summary(incident_id),
        "can": {
            "edit": can_edit,
            "administer": service.can_administer(user, incident),
        },
    }
    if can_edit:
        detail["organizations"] = service.all_organizations()
        detail["candidates"] = service.candidates(incident)
        detail["available_sources"] = [
            {"id": item.id, "name": item.name, "drone_type": item.drone_type}
            for item in config.sources
            if item.enabled and item.id not in assigned and can_operate_source(user, item)
        ]
        detail["checklist_templates"] = [
            {"id": item["id"], "title": item["title"], "item_count": item["item_count"]}
            for item in ChecklistService(service).visible_templates(user)
            if not item["archived"]
        ]
        detail["guest_links"] = [
            link.public() for link in guest_link_store.list()
            if link.incident_id == incident_id
        ]
    return detail


# ----------------------------------------------------------------------
# Wetter und Benachrichtigung
# ----------------------------------------------------------------------


def capture_weather(incident: dict, actor: str = "System") -> bool:
    settings = config.weather
    if not settings.enabled:
        return False
    if incident.get("latitude") is not None and incident.get("longitude") is not None:
        location = {
            "latitude": incident["latitude"],
            "longitude": incident["longitude"],
            "name": incident.get("address") or "Einsatzort",
        }
    else:
        location = default_location(settings)
    try:
        report = weather_service.report(settings, location["latitude"], location["longitude"])
    except Exception:  # Wetter darf das Anlegen nie verhindern.
        logger.exception("Wetter für Einsatz %s nicht erfasst.", incident["id"])
        return False
    snapshot = {
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "location": location,
        "current": report.get("current"),
        "derived": report.get("derived"),
        "assessment": report.get("assessment"),
        "alerts": [
            {"event": item.get("event"), "headline": item.get("headline")}
            for item in report.get("alerts") or []
        ],
        "kp": report.get("kp"),
        "sun": report.get("sun"),
        "attribution": report.get("attribution"),
    }
    _service().set_weather(incident["id"], snapshot, actor)
    return True


def _announce(incident: dict) -> None:
    title = incident["keyword"] or incident["title"] or "Einsatz"
    place = f" · {incident['address']}" if incident["address"] else ""
    kind = "Übung" if incident.get("exercise") else "Einsatz"
    server_event_log.record(
        "info" if incident.get("exercise") else "warning",
        f"🚨 {kind} {incident['code']} angelegt: {title}{place}",
        actor=incident["created_by"],
        organization_id=incident["lead_organization_id"],
    )
    push_service.enqueue(
        Notice(
            event="incident_started",
            subject=f"{kind}: {title}",
            body=(incident["address"] or "Neuer Drohneneinsatz") + f" ({incident['code']})",
            incident_id=incident["id"],
            url=f"/#incidents/{incident['id']}",
        )
    )


# ----------------------------------------------------------------------
# Übersicht und Anlegen
# ----------------------------------------------------------------------


class IncidentCreate(BaseModel):
    lead_organization_id: int
    alarm_at: str | None = Field(default=None, max_length=40)
    keyword: str = Field(default="", max_length=80)
    title: str = Field(default="", max_length=120)
    address: str = Field(default="", max_length=200)
    latitude: float | None = None
    longitude: float | None = None
    alarm_text: str = Field(default="", max_length=4000)
    alerted_units: str = Field(default="", max_length=300)
    dispatch_number: str = Field(default="", max_length=40)
    exercise: bool = False
    source_ids: list[str] = Field(default_factory=list, max_length=200)


class IncidentUpdate(BaseModel):
    alarm_at: str | None = Field(default=None, max_length=40)
    keyword: str | None = Field(default=None, max_length=80)
    title: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=200)
    alarm_text: str | None = Field(default=None, max_length=4000)
    alerted_units: str | None = Field(default=None, max_length=300)
    dispatch_number: str | None = Field(default=None, max_length=40)
    summary: str | None = Field(default=None, max_length=8000)
    lead_organization_id: int | None = None
    exercise: bool | None = None


class PositionUpdate(BaseModel):
    latitude: float | None = None
    longitude: float | None = None


@router.get("")
async def list_incidents(request: Request) -> dict:
    user = _user(request)
    service = _service()
    items = await run_in_threadpool(service.visible, user)
    lead_ids = set(user.get("org_operate") or [])
    unrestricted = user.get("platform_admin") or "org_view" not in user
    organizations = await run_in_threadpool(service.all_organizations)
    return {
        "incidents": [_summary(item) for item in items],
        "lead_options": [
            item for item in organizations
            if unrestricted or item["id"] in lead_ids
        ],
        "roles": INCIDENT_ROLES,
        "statuses": INCIDENT_STATUS,
        "sources": [
            {"id": item.id, "name": item.name}
            for item in config.sources
            if item.enabled and can_operate_source(user, item)
        ],
    }


@router.post("")
async def create_incident(payload: IncidentCreate, request: Request, background: BackgroundTasks) -> dict:
    user = _user(request)
    service = _service()
    data = payload.model_dump(exclude={"source_ids"})
    incident = await _call(service.create, user, **data)
    for source_id in payload.source_ids:
        source = _source(source_id)
        if source is not None and source.enabled and can_operate_source(user, source):
            incident = await _call(service.add_source, user, incident["id"], source)
    background.add_task(capture_weather, incident, "System")
    await run_in_threadpool(_announce, incident)
    return {"success": True, "incident": _summary(incident)}


@router.get("/{incident_id}")
async def get_incident(incident_id: int, request: Request) -> dict:
    user = _user(request)
    return await _call(_detail, user, incident_id)


@router.patch("/{incident_id}")
async def update_incident(incident_id: int, payload: IncidentUpdate, request: Request) -> dict:
    user = _user(request)
    changes = payload.model_dump(exclude_unset=True)
    await _call(_service().update, user, incident_id, **changes)
    return await _call(_detail, user, incident_id)


class StatusUpdate(BaseModel):
    status: str = Field(max_length=16)
    ended_at: str | None = Field(default=None, max_length=40)


@router.post("/{incident_id}/status")
async def change_status(incident_id: int, payload: StatusUpdate, request: Request) -> dict:
    user = _user(request)
    incident = await _call(_service().set_status, user, incident_id, payload.status, ended_at=payload.ended_at)
    if incident["status"] != "running":
        revoked = await run_in_threadpool(
            guest_link_store.revoke_for_incident, incident_id, "Einsatzende"
        )
        if revoked:
            await run_in_threadpool(
                _service().record, incident_id,
                f"{revoked} Gastlink(s) mit dem Einsatzende gesperrt", kind="guest",
            )
    if payload.status == "ended":
        server_event_log.record(
            "info",
            f"🚨 Einsatz {incident['code']} beendet",
            actor=user["username"],
            organization_id=incident["lead_organization_id"],
        )
    return await _call(_detail, user, incident_id)


@router.delete("/{incident_id}")
async def delete_incident(incident_id: int, request: Request) -> dict:
    user = _user(request)
    incident = await _call(_service().delete, user, incident_id)
    await run_in_threadpool(guest_link_store.revoke_for_incident, incident_id, user["username"])
    server_event_log.record(
        "warning",
        f"🚨 Einsatz {incident['code']} gelöscht",
        actor=user["username"],
        organization_id=incident["lead_organization_id"],
    )
    return {"success": True}


# ----------------------------------------------------------------------
# Wehren, Personen, Drohnen, Verlauf
# ----------------------------------------------------------------------


class OrganizationIn(BaseModel):
    organization_id: int


@router.post("/{incident_id}/organizations")
async def add_organization(incident_id: int, payload: OrganizationIn, request: Request) -> dict:
    user = _user(request)
    await _call(_service().add_organization, user, incident_id, payload.organization_id)
    return await _call(_detail, user, incident_id)


@router.delete("/{incident_id}/organizations/{organization_id}")
async def remove_organization(incident_id: int, organization_id: int, request: Request) -> dict:
    user = _user(request)
    await _call(_service().remove_organization, user, incident_id, organization_id)
    return await _call(_detail, user, incident_id)


class ParticipantIn(BaseModel):
    role: str = Field(max_length=40)
    user_id: int | None = None
    name: str = Field(default="", max_length=80)
    organization_id: int | None = None
    from_at: str | None = Field(default=None, max_length=40)
    until_at: str | None = Field(default=None, max_length=40)
    note: str = Field(default="", max_length=200)


class ParticipantUpdate(BaseModel):
    role: str | None = Field(default=None, max_length=40)
    from_at: str | None = Field(default=None, max_length=40)
    until_at: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=200)


@router.post("/{incident_id}/participants")
async def add_participant(incident_id: int, payload: ParticipantIn, request: Request) -> dict:
    user = _user(request)
    await _call(_service().add_participant, user, incident_id, **payload.model_dump())
    return await _call(_detail, user, incident_id)


@router.patch("/{incident_id}/participants/{participant_id}")
async def update_participant(
    incident_id: int, participant_id: int, payload: ParticipantUpdate, request: Request,
) -> dict:
    user = _user(request)
    await _call(
        _service().update_participant, user, incident_id, participant_id,
        **payload.model_dump(exclude_unset=True),
    )
    return await _call(_detail, user, incident_id)


@router.delete("/{incident_id}/participants/{participant_id}")
async def remove_participant(incident_id: int, participant_id: int, request: Request) -> dict:
    user = _user(request)
    await _call(_service().remove_participant, user, incident_id, participant_id)
    return await _call(_detail, user, incident_id)


class SourceIn(BaseModel):
    source_id: str = Field(max_length=64)


@router.post("/{incident_id}/sources")
async def add_source(incident_id: int, payload: SourceIn, request: Request) -> dict:
    user = _user(request)
    source = _source(payload.source_id)
    if source is None or not source.enabled:
        raise HTTPException(status_code=422, detail="Unbekannte oder deaktivierte Drohne.")
    if not can_operate_source(user, source):
        raise HTTPException(
            status_code=403,
            detail="Drohnen einer anderen Wehr ordnet deren Drohnenteam zu.",
        )
    await _call(_service().add_source, user, incident_id, source)
    return await _call(_detail, user, incident_id)


@router.delete("/{incident_id}/sources/{source_id}")
async def remove_source(incident_id: int, source_id: str, request: Request) -> dict:
    user = _user(request)
    await _call(_service().remove_source, user, incident_id, source_id)
    return await _call(_detail, user, incident_id)


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/{incident_id}/notes")
async def add_note(incident_id: int, payload: NoteIn, request: Request) -> dict:
    user = _user(request)
    await _call(_service().add_note, user, incident_id, payload.text)
    return await _call(_detail, user, incident_id)


@router.post("/{incident_id}/weather")
async def refresh_weather(incident_id: int, request: Request) -> dict:
    user = _user(request)
    incident = await _call(_service().require, user, incident_id, edit=True)
    captured = await run_in_threadpool(capture_weather, incident, _actor(user))
    if not captured:
        raise HTTPException(
            status_code=503,
            detail="Wetter konnte nicht erfasst werden (Wettermodul aus oder nicht erreichbar).",
        )
    return await _call(_detail, user, incident_id)


@router.get("/{incident_id}/media/{name}")
async def incident_media(incident_id: int, name: str, request: Request, download: bool = False):
    user = _user(request)
    incident = await _call(_service().require, user, incident_id)
    items = await run_in_threadpool(_incident_media, incident)
    item = next((entry for entry in items if entry["name"] == name), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Aufnahme gehört nicht zu diesem Einsatz.")
    library = snapshot_library if item["type"] == "snapshot" else recording_library
    file = library.get_file(name)
    if file is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.")
    return FileResponse(
        path=file,
        filename=file.name if download else None,
        media_type="image/jpeg" if item["type"] == "snapshot" else "video/mp4",
    )


# ----------------------------------------------------------------------
# Einsatzkarte (Quadranten)
# ----------------------------------------------------------------------


def map_state(incident: dict, since: int | None = None) -> dict:
    incident_map = _map()
    revision = incident_map.revision(incident["id"]) or 0
    if since is not None and since == revision:
        # Nichts geändert: kleine Antwort für den Abgleich alle paar Sekunden.
        # Der Status gehört dazu: Das Einsatzende zählt die Revision nicht hoch.
        return {
            "incident_id": incident["id"],
            "revision": revision,
            "changed": False,
            "status": incident["status"],
        }
    state = incident_map.state(incident)
    state.update(
        changed=True,
        code=incident["code"],
        keyword=incident["keyword"],
        exercise=bool(incident.get("exercise")),
        status=incident["status"],
    )
    return state


def _map_rights(user: dict, incident: dict) -> dict:
    """Zeichnen nur im laufenden Einsatz, Nachträge nur, solange er „beendet“ ist."""

    can_edit = _service().can_edit(user, incident)
    return {
        "can_edit": can_edit and incident["status"] == "running",
        "can_follow_up": can_edit and incident["status"] == "ended",
    }


@router.get("/{incident_id}/map")
async def get_map(incident_id: int, request: Request, since: int | None = None) -> dict:
    user = _user(request)
    incident = await _call(_service().require, user, incident_id)
    state = await run_in_threadpool(map_state, incident, since)
    state.update(_map_rights(user, incident))
    return state


class MapItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    geometry: dict
    status: str = Field(default="open", max_length=16)
    assignee: str = Field(default="", max_length=80)
    note: str = Field(default="", max_length=300)


class MapItemUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=40)
    geometry: dict | None = None
    status: str | None = Field(default=None, max_length=16)
    assignee: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=300)


class GridIn(BaseModel):
    west: float
    south: float
    east: float
    north: float
    rows: int = Field(ge=1, le=12)
    columns: int = Field(ge=1, le=12)
    prefix: str = Field(default="", max_length=10)


async def _map_response(user: dict, incident_id: int) -> dict:
    incident = await _call(_service().require, user, incident_id)
    state = await run_in_threadpool(map_state, incident, None)
    state.update(_map_rights(user, incident))
    return state


@router.post("/{incident_id}/map/items")
async def add_map_item(incident_id: int, payload: MapItemIn, request: Request) -> dict:
    user = _user(request)
    await _call(_map().add_item, user, incident_id, **payload.model_dump())
    return await _map_response(user, incident_id)


@router.post("/{incident_id}/map/grid")
async def add_map_grid(incident_id: int, payload: GridIn, request: Request) -> dict:
    user = _user(request)
    await _call(_map().add_grid, user, incident_id, **payload.model_dump())
    return await _map_response(user, incident_id)


@router.patch("/{incident_id}/map/items/{item_id}")
async def update_map_item(incident_id: int, item_id: int, payload: MapItemUpdate, request: Request) -> dict:
    user = _user(request)
    await _call(_map().update_item, user, incident_id, item_id, **payload.model_dump(exclude_unset=True))
    return await _map_response(user, incident_id)


@router.delete("/{incident_id}/map/items/{item_id}")
async def delete_map_item(incident_id: int, item_id: int, request: Request) -> dict:
    user = _user(request)
    await _call(_map().delete_item, user, incident_id, item_id)
    return await _map_response(user, incident_id)


@router.put("/{incident_id}/map/position")
async def set_map_position(incident_id: int, payload: PositionUpdate, request: Request) -> dict:
    user = _user(request)
    await _call(_map().require_editable, user, incident_id)
    await _call(
        _service().update, user, incident_id,
        latitude=payload.latitude, longitude=payload.longitude,
    )
    return await _map_response(user, incident_id)


# ----------------------------------------------------------------------
# Einsatz-Gastlinks
# ----------------------------------------------------------------------


class IncidentGuestLinkIn(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    hours: float = Field(gt=0, le=MAX_HOURS)


@router.post("/{incident_id}/guest-links")
async def create_incident_link(incident_id: int, payload: IncidentGuestLinkIn, request: Request) -> dict:
    user = _user(request)
    incident = await _call(_service().require, user, incident_id, edit=True)
    if incident["status"] != "running":
        raise HTTPException(status_code=422, detail="Gastlinks gibt es nur für laufende Einsätze.")
    link, token = await _call(
        guest_link_store.create,
        label=payload.label,
        source_ids=[],
        hours=payload.hours,
        created_by=user["username"],
        organization_id=incident["lead_organization_id"],
        incident_id=incident_id,
    )
    until = time.strftime("%d.%m. %H:%M", time.localtime(link.expires_at))
    await run_in_threadpool(
        _service().record, incident_id,
        f"Gastlink „{link.label}“ erstellt (gültig bis {until} Uhr, spätestens bis Einsatzende)",
        actor=_actor(user), kind="guest",
    )
    server_event_log.record(
        "info",
        f"🔗 Einsatz-Gastlink „{link.label}“ für {incident['code']} von {user['username']} erstellt",
        organization_id=incident["lead_organization_id"],
    )
    return {
        "success": True,
        "url": str(request.base_url).rstrip("/") + f"/g/{token}",
        "link": link.public(),
    }


@router.delete("/{incident_id}/guest-links/{link_id}")
async def revoke_incident_link(incident_id: int, link_id: str, request: Request) -> dict:
    user = _user(request)
    await _call(_service().require, user, incident_id, edit=True)
    link = next(
        (item for item in guest_link_store.list() if item.id == link_id and item.incident_id == incident_id),
        None,
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Gastlink nicht gefunden.")
    link = await run_in_threadpool(guest_link_store.revoke, link_id, user["username"])
    await run_in_threadpool(
        _service().record, incident_id, f"Gastlink „{link.label}“ gesperrt",
        actor=_actor(user), kind="guest",
    )
    return {"success": True, "link": link.public()}


# ----------------------------------------------------------------------
# Bericht
# ----------------------------------------------------------------------


def _local(value: str | None, with_date: bool = True) -> str:
    if not value:
        return "–"
    try:
        moment = parse_time(value)
    except IncidentError:
        return value
    return moment.strftime("%d.%m.%Y %H:%M" if with_date else "%H:%M")


@router.get("/{incident_id}/report", response_class=HTMLResponse)
async def incident_report(incident_id: int, request: Request):
    user = _user(request)
    detail = await _call(_detail, user, incident_id)
    return templates.TemplateResponse(
        request=request,
        name="incident_report.html",
        context={
            "version": VERSION,
            "detail": detail,
            "incident": detail["incident"],
            "local": _local,
            "printed_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "printed_by": _actor(user),
        },
    )
