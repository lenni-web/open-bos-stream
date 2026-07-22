from fastapi import APIRouter

from open_bos_stream.core.container import stream_service

router = APIRouter(
    prefix="/stream",
    tags=["Stream"],
)


@router.get("/status")
async def status():
    return {
        "running": stream_service.running,
        "pid": stream_service.pid,
    }


@router.post("/start")
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


@router.post("/stop")
async def stop():
    stream_service.stop()

    return {
        "success": True,
        "running": stream_service.running,
    }
