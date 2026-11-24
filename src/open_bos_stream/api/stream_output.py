from fastapi import APIRouter, HTTPException, Request

from open_bos_stream.core.container import (
    server_event_log,
    stream_output_service,
)
from open_bos_stream.auth.roles import SUPERADMIN

router = APIRouter(
    dependencies=[SUPERADMIN],
    prefix="/stream-output",
    tags=["Stream Output"],
)


@router.get("/status")
async def status():
    return stream_output_service.status


@router.post("/{name}/start")
async def start(name: str, request: Request):
    try:
        stream_output_service.start(name)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "stream_output_start_failed",
                "message": str(exc),
            },
        ) from exc
    server_event_log.record(
        "success",
        f"📺 Weiterleitung „{name}“ gestartet",
        actor=request.state.user["username"],
    )
    return {"success": True}


@router.post("/{name}/stop")
async def stop(name: str, request: Request):
    try:
        stream_output_service.stop(name)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "stream_output_stop_failed",
                "message": str(exc),
            },
        ) from exc
    server_event_log.record(
        "info",
        f"📺 Weiterleitung „{name}“ gestoppt",
        actor=request.state.user["username"],
    )
    return {"success": True}


@router.post("/stop-all")
async def stop_all():
    stream_output_service.stop_all()
    return {"success": True}
