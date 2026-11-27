"""Gastlinks: erstellen, verwalten und als Gast ansehen."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from open_bos_stream.auth.guest_access import (
    can_operate_source,
    guest_sources,
    is_guest,
    is_restricted,
)
from open_bos_stream.auth.guest_links import MAX_HOURS, GuestLinkError
from open_bos_stream.auth.middleware import secure_cookies
from open_bos_stream.auth.roles import GUEST, OPERATOR, PUBLIC
from open_bos_stream.core.container import (
    auth_service,
    config,
    dashboard_service,
    guest_link_store,
    server_event_log,
)
from open_bos_stream.version import VERSION

router = APIRouter(tags=["Gastzugang"])
logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="src/open_bos_stream/templates")

# Felder, die die Gastansicht für die Videokacheln braucht. Technische
# Angaben wie Empfangsadressen oder Laufzeitdaten bleiben intern.
GUEST_SOURCE_FIELDS = (
    "id",
    "name",
    "drone_type",
    "type",
    "profile",
    "preview_active",
    "viewer_path",
    "fullscreen_viewer_path",
    "ready",
    "online",
    "viewers",
    "codec",
    "width",
    "height",
    "health",
)


class GuestLinkCreate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    source_ids: list[str] = Field(min_length=1, max_length=200)
    hours: float = Field(gt=0, le=MAX_HOURS)


def _link_url(request: Request, token: str) -> str:
    return str(request.base_url).rstrip("/") + f"/g/{token}"


def _source_names() -> dict[str, str]:
    return {source.id: source.name for source in config.sources}


def _until(link) -> str:
    return time.strftime("%d.%m. %H:%M", time.localtime(link.expires_at))


def _describe(link) -> dict:
    data = link.public()
    names = _source_names()
    data["sources"] = [
        {"id": source_id, "name": names.get(source_id, source_id)}
        for source_id in link.source_ids
    ]
    return data


# ----------------------------------------------------------------------
# Verwaltung (Admins und Superadmins)
# ----------------------------------------------------------------------


def _may_manage(user: dict, link) -> bool:
    """Drohnenteam und Admins der Organisation des Links."""

    if not is_restricted(user) or user.get("server_admin"):
        return True
    return (
        link.organization_id in set(user.get("org_operate") or [])
        or (link.organization_id is None and link.created_by == user.get("username"))
    )


@router.get("/guest-links", dependencies=[OPERATOR])
async def list_guest_links(request: Request) -> dict:
    links = await run_in_threadpool(guest_link_store.list)
    user = request.state.user
    return {
        # Einsatz-Gastlinks verwaltet der Einsatz selbst.
        "links": [
            _describe(link)
            for link in links
            if link.incident_id is None and _may_manage(user, link)
        ],
        "max_hours": MAX_HOURS,
    }


@router.post("/guest-links", dependencies=[OPERATOR])
async def create_guest_link(payload: GuestLinkCreate, request: Request) -> dict:
    enabled = {source.id: source for source in config.sources if source.enabled}
    unknown = [item for item in payload.source_ids if item not in enabled]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail="Unbekannte oder deaktivierte Drohne ausgewählt.",
        )
    user = request.state.user
    chosen = [enabled[item] for item in payload.source_ids]
    if not all(can_operate_source(user, source) for source in chosen):
        raise HTTPException(
            status_code=403,
            detail="Gastlinks nur für Drohnen der eigenen Organisation.",
        )
    organization_id = next(
        (source.organization_id for source in chosen if source.organization_id),
        None,
    )
    creator = request.state.user["username"]
    try:
        link, token = await run_in_threadpool(
            lambda: guest_link_store.create(
                label=payload.label,
                source_ids=payload.source_ids,
                hours=payload.hours,
                created_by=creator,
                organization_id=organization_id,
            )
        )
    except GuestLinkError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    logger.info(
        "Gastlink „%s“ von %s erstellt (Drohnen: %s, gültig bis %s).",
        link.label,
        creator,
        ", ".join(link.source_ids),
        time.strftime("%d.%m.%Y %H:%M", time.localtime(link.expires_at)),
    )
    names = _source_names()
    server_event_log.record(
        "info",
        f"🔗 Gastlink „{link.label}“ von {creator} erstellt · "
        + ", ".join(names.get(item, item) for item in link.source_ids)
        + f" · gültig bis {_until(link)} Uhr",
        organization_id=link.organization_id,
    )
    return {
        "success": True,
        # Der Link wird nur einmal ausgeliefert; gespeichert ist nur der Hash.
        "url": _link_url(request, token),
        "link": _describe(link),
    }


@router.delete("/guest-links/{link_id}", dependencies=[OPERATOR])
async def revoke_guest_link(link_id: str, request: Request) -> dict:
    existing = next(
        (link for link in guest_link_store.list() if link.id == link_id),
        None,
    )
    if existing is not None and not _may_manage(request.state.user, existing):
        raise HTTPException(403, "Dieser Gastlink gehört zu einer anderen Organisation.")
    user = request.state.user["username"]
    try:
        link = await run_in_threadpool(
            guest_link_store.revoke,
            link_id,
            user,
        )
    except KeyError as exc:
        raise HTTPException(404, "Gastlink wurde nicht gefunden.") from exc
    logger.info("Gastlink „%s“ von %s gesperrt.", link.label, user)
    server_event_log.record(
        "warning",
        f"🔗 Gastlink „{link.label}“ von {user} gesperrt",
        organization_id=link.organization_id,
    )
    return {"success": True, "link": _describe(link)}


# ----------------------------------------------------------------------
# Gastzugang
# ----------------------------------------------------------------------


@router.get("/g/{token}", response_class=HTMLResponse, dependencies=[PUBLIC])
async def open_guest_link(token: str, request: Request):
    link = await run_in_threadpool(guest_link_store.find_by_token, token)
    incident = None
    if link is not None and link.incident_id is not None:
        incident = await run_in_threadpool(auth_service.incidents.get, link.incident_id)
        if incident is None or incident["status"] != "running":
            link = None
    if link is None:
        return templates.TemplateResponse(
            request=request,
            name="guest_invalid.html",
            context={"version": VERSION, "signed_in": None},
            status_code=410,
        )
    current = getattr(request.state, "user", None)
    if current and not is_guest(current):
        # Eine bestehende Anmeldung nicht durch die Gastsitzung ersetzen.
        return templates.TemplateResponse(
            request=request,
            name="guest_invalid.html",
            context={"version": VERSION, "signed_in": current["username"]},
            status_code=409,
        )
    logger.info("Gastlink „%s“ geöffnet.", link.label)
    server_event_log.record(
        "success",
        f"🔗 Gastlink „{link.label}“ geöffnet",
        organization_id=link.organization_id,
    )
    if incident is not None:
        await run_in_threadpool(
            auth_service.incidents.record,
            incident["id"],
            f"Gastlink „{link.label}“ geöffnet",
            kind="guest",
        )
    await run_in_threadpool(guest_link_store.touch, link.id)
    response = RedirectResponse("/guest", status_code=303)
    response.set_cookie(
        auth_service.COOKIE_NAME,
        auth_service.create_guest_token(link),
        max_age=max(1, int(link.expires_at - time.time())),
        httponly=True,
        # "lax", damit der Link auch aus Messenger oder E-Mail heraus
        # funktioniert (seitenübergreifender Aufruf mit Weiterleitung).
        samesite="lax",
        secure=secure_cookies(request),
        path="/",
    )
    return response


@router.get("/guest", response_class=HTMLResponse, dependencies=[GUEST])
async def guest_page(request: Request):
    user = request.state.user
    if not is_guest(user):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="guest.html",
        context={
            "version": VERSION,
            "user": user,
            "media_token": auth_service.create_media_token(user),
            "expires_at": int(user["expires_at"]),
        },
    )


@router.get("/guest/status", dependencies=[GUEST])
async def guest_status(request: Request) -> dict:
    user = request.state.user
    if not is_guest(user):
        raise HTTPException(403, "Nur für Gastzugänge.")
    await run_in_threadpool(guest_link_store.touch, user["guest_link"])
    status = await run_in_threadpool(dashboard_service.status)
    allowed = {source.id for source in guest_sources(user, config)}
    sources = [
        {
            key: item.get(key)
            for key in GUEST_SOURCE_FIELDS
        } | {"publish_url": ""}
        for item in status.get("sources", [])
        if item.get("id") in allowed
    ]
    result = {
        "label": user["username"].removeprefix("Gast: "),
        "expires_at": int(user["expires_at"]),
        "sources": sources,
        "incident": None,
    }
    if user.get("incident_id"):
        incident = await run_in_threadpool(auth_service.incidents.get, user["incident_id"])
        if incident:
            # Nur, was die externe Stelle zur Einordnung braucht.
            result["incident"] = {
                key: incident.get(key)
                for key in ("code", "keyword", "address", "alarm_at", "latitude", "longitude", "exercise")
            }
    return result


@router.get("/guest/incident-map", dependencies=[GUEST])
async def guest_incident_map(request: Request, since: int | None = None) -> dict:
    """Einsatzkarte für Einsatz-Gastlinks (nur lesen)."""

    from open_bos_stream.api.incidents import map_state

    user = request.state.user
    if not is_guest(user) or not user.get("incident_id"):
        raise HTTPException(404, "Kein Einsatz zu diesem Gastzugang.")
    incident = await run_in_threadpool(auth_service.incidents.get, user["incident_id"])
    if incident is None:
        raise HTTPException(404, "Einsatz nicht gefunden.")
    state = await run_in_threadpool(map_state, incident, since)
    state["can_edit"] = False
    return state


@router.get("/guest/incident-positions", dependencies=[GUEST])
async def guest_incident_positions(request: Request, after: int = 0) -> dict:
    """Drohnen für Einsatz-Gastlinks; Standorte von Personen bleiben intern."""

    from open_bos_stream.api.dji import drone_service

    user = request.state.user
    if not is_guest(user) or not user.get("incident_id"):
        raise HTTPException(404, "Kein Einsatz zu diesem Gastzugang.")
    incident = await run_in_threadpool(auth_service.incidents.get, user["incident_id"])
    if incident is None:
        raise HTTPException(404, "Einsatz nicht gefunden.")
    state = await run_in_threadpool(lambda: drone_service().positions(incident, after=max(0, after)))
    state["persons"] = []
    for drone in state["drones"]:
        drone["controller"] = None
    return state
