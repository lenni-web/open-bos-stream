import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from open_bos_stream.core.container import dashboard_service
from open_bos_stream.stream.probe import ProbeBusyError

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("/status")
async def status():
    return dashboard_service.status()


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
