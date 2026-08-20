from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from open_bos_stream.core.container import (
    health_service,
    system_administration_service,
    system_info_service,
)
from open_bos_stream.core.installation import (
    installation_profile,
    server_access_settings,
)

router = APIRouter(
    prefix="/system",
    tags=["System"],
)


@router.get("/health")
async def system_health():
    return await run_in_threadpool(health_service.health)


@router.get("/info")
async def system_info():
    return await run_in_threadpool(_system_info_payload)


@router.get("/stream-log")
async def stream_log():
    try:
        content = await run_in_threadpool(
            system_administration_service.stream_log
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "stream_log_unavailable",
                "message": f"Stream-Protokoll konnte nicht gelesen werden: {exc}",
            },
        ) from exc

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "content": content,
    }


@router.post("/reboot")
async def reboot_system():
    try:
        await run_in_threadpool(
            system_administration_service.schedule_reboot
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "reboot_failed",
                "message": f"Server-Neustart konnte nicht ausgelöst werden: {exc}",
            },
        ) from exc

    return {
        "success": True,
        "message": "Server-Neustart wurde für in wenigen Sekunden eingeplant.",
    }


def _system_info_payload() -> dict:
    info = system_info_service.info().model_dump()
    info["installation_profile"] = installation_profile()
    info["server_access"] = server_access_settings()
    return info
