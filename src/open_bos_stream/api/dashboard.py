from fastapi import APIRouter

from open_bos_stream.core.container import dashboard_service

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("/status")
async def status():
    return dashboard_service.status()
