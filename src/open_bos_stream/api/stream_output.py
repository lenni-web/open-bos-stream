from fastapi import APIRouter

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
    stream_output_service.start(name)
    return {"success": True}


@router.post("/{name}/stop")
async def stop(name: str):
    stream_output_service.stop(name)
    return {"success": True}


@router.post("/stop-all")
async def stop_all():
    stream_output_service.stop_all()
    return {"success": True}
