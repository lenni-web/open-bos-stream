import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from open_bos_stream.core.container import (
    dashboard_service,
    fullscreen_relay_manager,
    server_event_log,
)
from open_bos_stream.auth.service import ROLE_LEVEL
from open_bos_stream.stream.probe import ProbeBusyError
from open_bos_stream.auth.guest_access import require_guest_source
from open_bos_stream.auth.roles import ADMIN, GUEST, VIEWER

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("/status", dependencies=[VIEWER])
async def status(request: Request, events_after: int | None = None):
    data = await run_in_threadpool(dashboard_service.status)
    user = request.state.user
    if ROLE_LEVEL.get(user.get("role"), -1) >= ROLE_LEVEL["admin"]:
        # Kopie: der Status wird zwischen Anfragen zwischengespeichert.
        # Der Browser fragt nur Einträge nach seinem letzten Stand ab.
        data = {
            **data,
            "server_events": server_event_log.since(events_after),
        }
    return data


@router.post("/sources/{source_id}/probe", dependencies=[ADMIN])
async def probe_source(source_id: str):
    try:
        return await run_in_threadpool(
            dashboard_service.probe_source,
            source_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="Aktive Quelle wurde nicht gefunden.",
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
    require_guest_source(request.state.user, source_id)
    try:
        return await run_in_threadpool(
            fullscreen_relay_manager.acquire,
            source_id,
        )
    except KeyError as exc:
        raise HTTPException(404, "Aktive Quelle wurde nicht gefunden.") from exc
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
    require_guest_source(request.state.user, source_id)
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
    require_guest_source(request.state.user, source_id)
    await run_in_threadpool(
        fullscreen_relay_manager.release,
        source_id,
        lease_id,
    )
    return {"success": True}


@router.get("/diagnostics", dependencies=[ADMIN])
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
