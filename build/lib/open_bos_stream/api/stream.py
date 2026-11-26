from fastapi import APIRouter

from open_bos_stream.core.container import stream_service
from open_bos_stream.auth.roles import SERVER_ADMIN, VIEWER

router = APIRouter(
    prefix="/stream",
    tags=["Stream"],
)


@router.get("/status", dependencies=[VIEWER])
async def status():
    return {
        "running": stream_service.running,
        "pid": stream_service.pid,
        "passthrough": not stream_service.managed,
        "controllable": stream_service.managed,
    }


@router.post("/start", dependencies=[SERVER_ADMIN])
async def start():
    try:
        running = stream_service.start()

        return {
            "success": running,
            "running": running,
        }

    except RuntimeError as exc:
        return {
            "success": False,
            "error": str(exc),
        }


@router.post("/stop", dependencies=[SERVER_ADMIN])
async def stop():
    try:
        stopped = stream_service.stop()

        return {
            "success": stopped,
            "running": stream_service.running,
        }

    except RuntimeError as exc:
        return {
            "success": False,
            "running": stream_service.running,
            "error": str(exc),
        }
