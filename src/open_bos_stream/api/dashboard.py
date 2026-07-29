import json
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import Response

from open_bos_stream.core.container import dashboard_service

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("/status")
async def status():
    return dashboard_service.status()


@router.get("/diagnostics")
async def diagnostics():
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **dashboard_service.status(),
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
