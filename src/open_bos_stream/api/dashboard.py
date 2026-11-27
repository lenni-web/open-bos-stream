import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from open_bos_stream.system.load import message as load_message
from open_bos_stream.core.container import (
    auth_service,
    config as runtime_config,
    dashboard_service,
    fullscreen_relay_manager,
    server_event_log,
)
from open_bos_stream.auth.service import ROLE_LEVEL
from open_bos_stream.stream.probe import ProbeBusyError
from open_bos_stream.auth.guest_access import (
    is_restricted,
    require_source_access,
    visible_source_ids,
)
from open_bos_stream.auth.roles import ADMIN, GUEST, VIEWER, SERVER_ADMIN

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("/status", dependencies=[VIEWER])
async def status(request: Request, events_after: int | None = None):
    data = await run_in_threadpool(dashboard_service.status)
    user = request.state.user
    visible = visible_source_ids(user, runtime_config)
    if visible is not None:
        # Kopie: der Status wird zwischen Anfragen zwischengespeichert.
        data = filter_status_sources(data, visible)
    data = with_organization_names(data)
    if user.get("role") == "superadmin":
        # Das Ereignisprotokoll ist nur für Superadmins. Der Browser fragt
        # nur Einträge nach seinem letzten Stand ab.
        data = {
            **data,
            "server_events": server_event_log.since(events_after, None),
        }
    return data


def with_organization_names(data: dict) -> dict:
    """Kurzname der Wehr je Quelle für Übersicht und Livebilder."""

    sources = data.get("sources") or []
    if not any(item.get("organization_id") for item in sources):
        return data
    try:
        names = {
            item["id"]: item["short_name"] or item["name"]
            for item in auth_service.ready().organizations()
        }
    except Exception:  # Anzeige ist optional, der Status nicht.
        return data
    return {
        **data,
        "sources": [
            {**item, "organization_name": names.get(item.get("organization_id"))}
            for item in sources
        ],
    }


def filter_status_sources(data: dict, visible: set[str]) -> dict:
    """Status ohne Quellen anderer Organisationen."""

    def keep(items):
        return [
            item for item in items or []
            if item.get("source_id", item.get("id")) in visible
        ]

    load = data.get("server_load")
    if load:
        # Gesamtzahl der Quellen anderer Wehren nicht verraten.
        load = {
            **load,
            "active_sources": None,
            "message": load_message(load.get("level", "ok"), load.get("reasons") or [], 0),
        }
    return {
        **data,
        "sources": keep(data.get("sources")),
        "recordings": keep(data.get("recordings")),
        "stream_outputs": keep(data.get("stream_outputs")),
        "server_load": load,
    }


@router.post("/sources/{source_id}/probe", dependencies=[ADMIN])
async def probe_source(source_id: str, request: Request):
    require_source_access(request.state.user, source_id, runtime_config)
    try:
        return await run_in_threadpool(
            dashboard_service.probe_source,
            source_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="Aktive Drohne wurde nicht gefunden.",
        ) from exc
    except ProbeBusyError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "source_probe_busy",
                "message": str(exc),
            },
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "source_probe_unavailable",
                "message": str(exc),
            },
        ) from exc


@router.post("/sources/{source_id}/fullscreen", dependencies=[GUEST])
async def acquire_fullscreen_stream(source_id: str, request: Request):
    require_source_access(request.state.user, source_id, runtime_config)
    try:
        return await run_in_threadpool(
            fullscreen_relay_manager.acquire,
            source_id,
        )
    except KeyError as exc:
        raise HTTPException(404, "Aktive Drohne wurde nicht gefunden.") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            503,
            f"Hauptstream konnte nicht gestartet werden: {exc}",
        ) from exc


@router.get("/sources/{source_id}/fullscreen/{lease_id}", dependencies=[GUEST])
async def fullscreen_stream_status(
    source_id: str,
    lease_id: str,
    request: Request,
):
    require_source_access(request.state.user, source_id, runtime_config)
    try:
        return await run_in_threadpool(
            fullscreen_relay_manager.status,
            source_id,
            lease_id,
        )
    except KeyError as exc:
        raise HTTPException(404, "Vollbild-Anforderung ist abgelaufen.") from exc


@router.delete("/sources/{source_id}/fullscreen/{lease_id}", dependencies=[GUEST])
async def release_fullscreen_stream(
    source_id: str,
    lease_id: str,
    request: Request,
):
    require_source_access(request.state.user, source_id, runtime_config)
    await run_in_threadpool(
        fullscreen_relay_manager.release,
        source_id,
        lease_id,
    )
    return {"success": True}


@router.get("/diagnostics", dependencies=[SERVER_ADMIN])
async def diagnostics():
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **await run_in_threadpool(dashboard_service.status),
    }
    return Response(
        content=json.dumps(payload, indent=2, ensure_ascii=False),
        media_type="text/plain",
        headers={
            "Content-Disposition": (
                "attachment; filename=open-bos-diagnostics.txt"
            )
        },
    )
