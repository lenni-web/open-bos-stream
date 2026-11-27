"""DJI-Anbindung: Anmeldeseite für Pilot 2, Geräte, Positionen, Export."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from open_bos_stream.auth.guest_access import is_restricted
from open_bos_stream.auth.roles import ADMIN, OPERATOR, PUBLIC, VIEWER
from open_bos_stream.core.container import auth_service, config, server_event_log
from open_bos_stream.dji.config import load_config
from open_bos_stream.dji.mqtt import BrokerClient
from open_bos_stream.dji.service import DroneService
from open_bos_stream.incidents.drone_history import drone_history
from open_bos_stream.incidents.service import IncidentAccessError, IncidentError
from open_bos_stream.version import VERSION

router = APIRouter(tags=["DJI und Positionen"])
templates = Jinja2Templates(directory="src/open_bos_stream/templates")

_instance: DroneService | None = None
_broker: BrokerClient | None = None


def drone_service() -> DroneService:
    global _instance
    auth_service.ready()
    if _instance is None or _instance.incidents is not auth_service.incidents:
        _instance = DroneService(auth_service.incidents)
    return _instance


def start_broker() -> None:
    """Beim Anwendungsstart: nur mit eingerichteter ``config/dji.yaml``."""

    global _broker
    dji = load_config()
    if not dji.enabled:
        return
    service = drone_service()
    service.purge()
    _broker = BrokerClient(dji, lambda topic, payload: drone_service().handle(topic, payload))
    _broker.start()


def stop_broker() -> None:
    global _broker
    if _broker is not None:
        _broker.stop()
        _broker = None


async def _call(function, *args, **kwargs):
    try:
        return await run_in_threadpool(lambda: function(*args, **kwargs))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'\"")) from exc
    except IncidentAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except IncidentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _user(request: Request) -> dict:
    user = request.state.user
    if user.get("role") == "guest":
        raise HTTPException(status_code=403, detail="Nur für angemeldete Konten.")
    return user


# ----------------------------------------------------------------------
# Anmeldung der Fernsteuerung
# ----------------------------------------------------------------------


@router.get("/dji", response_class=HTMLResponse, dependencies=[PUBLIC])
async def pilot_page(request: Request):
    """Seite für Pilot 2; enthält selbst keine Zugangsdaten."""

    return templates.TemplateResponse(
        request=request, name="dji_pilot.html", context={"version": VERSION},
    )


@router.get("/api/dji/pilot-config", dependencies=[OPERATOR])
async def pilot_config(request: Request):
    user = _user(request)
    dji = load_config()
    if not dji.licensed:
        raise HTTPException(
            status_code=503,
            detail="Die DJI-Anbindung ist auf dem Server noch nicht eingerichtet.",
        )
    server_event_log.record(
        "info", "🛩️ Anmeldung einer DJI-Fernsteuerung gestartet", actor=user["username"],
    )
    return JSONResponse(
        {
            "app_id": dji.app_id,
            "app_key": dji.app_key,
            "license": dji.license,
            "platform_name": dji.platform_name,
            "workspace_id": dji.workspace(),
            "workspace_name": user.get("display_name") or user["username"],
            "mqtt": {
                "host": dji.public_address(request.url.hostname or ""),
                "username": dji.pilot_username,
                "password": dji.pilot_password,
            },
        },
        headers={"Cache-Control": "no-store"},
    )


# ----------------------------------------------------------------------
# Quellen der eigenen Wehr (nur lesen)
# ----------------------------------------------------------------------


def _visible_sources(user: dict) -> list:
    own = set(user.get("org_view") or [])
    return [
        source for source in config.sources
        if not is_restricted(user) or source.organization_id in own
    ]


@router.get("/api/drones/sources", dependencies=[VIEWER])
async def own_sources(request: Request) -> dict:
    """Name, Typ und Wehr – bewusst ohne Adressen und Sende-Schlüssel."""

    user = _user(request)
    service = drone_service().incidents
    return {
        "sources": [
            {
                "id": source.id,
                "name": source.name,
                "drone_type": source.drone_type,
                "enabled": source.enabled,
                "organization_name": (
                    await run_in_threadpool(service.organization_label, source.organization_id)
                    if source.organization_id else ""
                ),
            }
            for source in _visible_sources(user)
        ]
    }


@router.get("/api/drones/history", dependencies=[VIEWER])
async def history(request: Request) -> dict:
    """Einsätze je Drohne mit Datum und beteiligten Personen."""

    user = _user(request)
    sources = [source.id for source in _visible_sources(user)]

    def load() -> dict:
        service = drone_service()
        serials = [item["serial"] for item in service.devices(user) if item["kind"] == "aircraft"]
        return drone_history(service.incidents, user, source_ids=sources, serials=serials)

    return await run_in_threadpool(load)


# ----------------------------------------------------------------------
# Geräte
# ----------------------------------------------------------------------


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    organization_id: int | None = None
    blocked: bool | None = None


async def _devices(user: dict) -> dict:
    service = drone_service()
    dji = load_config()
    organizations = await run_in_threadpool(service.incidents.all_organizations)
    managed = set(user.get("org_admin") or [])
    unrestricted = user.get("platform_admin") or user.get("server_admin") or "org_view" not in user
    return {
        "devices": await run_in_threadpool(service.devices, user),
        "organizations": [
            {"id": item["id"], "name": item["short_name"] or item["name"]}
            for item in organizations if unrestricted or item["id"] in managed
        ],
        "organization_names": {item["id"]: item["short_name"] or item["name"] for item in organizations},
        "configured": dji.licensed,
        "broker_connected": bool(_broker and _broker.connected),
    }


@router.get("/api/dji/devices", dependencies=[VIEWER])
async def list_devices(request: Request) -> dict:
    return await _devices(_user(request))


@router.patch("/api/dji/devices/{serial}", dependencies=[ADMIN])
async def update_device(serial: str, payload: DeviceUpdate, request: Request) -> dict:
    user = _user(request)
    await _call(drone_service().update_device, user, serial, **payload.model_dump(exclude_unset=True))
    return await _devices(user)


@router.delete("/api/dji/devices/{serial}", dependencies=[ADMIN])
async def delete_device(serial: str, request: Request) -> dict:
    user = _user(request)
    await _call(drone_service().delete_device, user, serial)
    return await _devices(user)


@router.get("/api/dji/live", dependencies=[VIEWER])
async def live_drones(request: Request) -> dict:
    """Aktuell sendende Drohnen für die Karte ohne gewählten Einsatz."""

    devices = await run_in_threadpool(drone_service().devices, _user(request))
    return {
        "drones": [
            {"serial": item["serial"], "name": item["name"] or item["model"], "state": item["state"]}
            for item in devices
            if item["kind"] == "aircraft" and item["state"]["online"] and "latitude" in item["state"]
        ]
    }


# ----------------------------------------------------------------------
# Einsatz: Positionen, Zuordnung, Standort, Export
# ----------------------------------------------------------------------


class LocationIn(BaseModel):
    latitude: float
    longitude: float
    accuracy: float | None = None


def _incident_drones(user: dict, incident_id: int) -> dict:
    service = drone_service()
    incident = service.incidents.require(user, incident_id)
    can_edit = service.incidents.can_edit(user, incident)
    assignments = service.assignments(incident_id)
    live = {item["serial"]: item for item in service.devices(user)}
    for entry in assignments:
        entry["state"] = (live.get(entry["serial"]) or {}).get("state") or {"online": False}
    available = []
    if can_edit and incident["status"] == "running":
        active = {entry["serial"] for entry in assignments if entry["active"]}
        operate = set(user.get("org_operate") or [])
        everything = user.get("platform_admin") or user.get("server_admin") or "org_view" not in user
        available = [
            {"serial": item["serial"], "name": item["name"] or item["model"], "online": item["state"]["online"]}
            for item in live.values()
            if item["kind"] == "aircraft" and not item["blocked"] and item["organization_id"]
            and item["serial"] not in active and (everything or item["organization_id"] in operate)
        ]
    return {
        "drones": assignments,
        "summary": service.summary(incident_id),
        "available": available,
        "can_edit": can_edit,
        "running": incident["status"] == "running",
    }


@router.get("/api/incidents/{incident_id}/drones", dependencies=[VIEWER])
async def incident_drone_list(incident_id: int, request: Request) -> dict:
    return await _call(_incident_drones, _user(request), incident_id)


@router.post("/api/incidents/{incident_id}/drones/{serial}", dependencies=[VIEWER])
async def assign_drone(incident_id: int, serial: str, request: Request) -> dict:
    user = _user(request)
    await _call(drone_service().assign, user, incident_id, serial)
    return await _call(_incident_drones, user, incident_id)


@router.delete("/api/incidents/{incident_id}/drones/{serial}", dependencies=[VIEWER])
async def release_drone(incident_id: int, serial: str, request: Request) -> dict:
    user = _user(request)
    await _call(drone_service().release, user, incident_id, serial)
    return await _call(_incident_drones, user, incident_id)


@router.get("/api/incidents/{incident_id}/positions", dependencies=[VIEWER])
async def incident_positions(incident_id: int, request: Request, after: int = 0) -> dict:
    service = drone_service()
    incident = await _call(service.incidents.require, _user(request), incident_id)
    return await run_in_threadpool(lambda: service.positions(incident, after=max(0, after)))


@router.put("/api/incidents/{incident_id}/location", dependencies=[VIEWER])
async def share_location(incident_id: int, payload: LocationIn, request: Request) -> dict:
    await _call(
        drone_service().share_location, _user(request), incident_id,
        payload.latitude, payload.longitude, payload.accuracy,
    )
    return {"success": True}


@router.delete("/api/incidents/{incident_id}/location", dependencies=[VIEWER])
async def stop_location(incident_id: int, request: Request) -> dict:
    drone_service().stop_sharing(_user(request), incident_id)
    return {"success": True}


async def _export(incident_id: int, request: Request, kind: str) -> StreamingResponse:
    service = drone_service()
    incident = await _call(service.incidents.require, _user(request), incident_id)
    rows, media_type = (
        (service.export_csv, "text/csv; charset=utf-8") if kind == "csv"
        else (service.export_jsonl, "application/x-ndjson")
    )
    name = f"drohnendaten_{incident['code']}.{kind}"
    return StreamingResponse(
        rows(incident_id),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/api/incidents/{incident_id}/telemetry.csv", dependencies=[VIEWER])
async def export_csv(incident_id: int, request: Request):
    return await _export(incident_id, request, "csv")


@router.get("/api/incidents/{incident_id}/telemetry.jsonl", dependencies=[VIEWER])
async def export_jsonl(incident_id: int, request: Request):
    return await _export(incident_id, request, "jsonl")
