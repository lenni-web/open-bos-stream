from fastapi import APIRouter, HTTPException

from open_bos_stream.core.container import (
    stream_output_service,
)

router = APIRouter(
    prefix="/stream-output",
    tags=["Stream Output"],
)


@router.get("/status")
async def status():
    return stream_output_service.status


@router.post("/{name}/start")
async def start(name: str):
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
    return {"success": True}


@router.post("/{name}/stop")
async def stop(name: str):
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
    return {"success": True}


@router.post("/stop-all")
async def stop_all():
    stream_output_service.stop_all()
    return {"success": True}
