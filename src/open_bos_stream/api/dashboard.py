import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from open_bos_stream.core.container import (
    dashboard_service,
    fullscreen_relay_manager,
)
from open_bos_stream.stream.probe import ProbeBusyError

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("/status")
async def status():
    return await run_in_threadpool(dashboard_service.status)


@router.post("/sources/{source_id}/probe")
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


@router.post("/sources/{source_id}/fullscreen")
async def acquire_fullscreen_stream(source_id: str):
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


@router.get("/sources/{source_id}/fullscreen/{lease_id}")
async def fullscreen_stream_status(source_id: str, lease_id: str):
    try:
        return await run_in_threadpool(
            fullscreen_relay_manager.status,
            source_id,
            lease_id,
        )
    except KeyError as exc:
        raise HTTPException(404, "Vollbild-Anforderung ist abgelaufen.") from exc


@router.delete("/sources/{source_id}/fullscreen/{lease_id}")
async def release_fullscreen_stream(source_id: str, lease_id: str):
    await run_in_threadpool(
        fullscreen_relay_manager.release,
        source_id,
        lease_id,
    )
    return {"success": True}


@router.get("/diagnostics")
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
