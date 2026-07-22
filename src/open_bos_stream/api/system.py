from fastapi import APIRouter

from open_bos_stream.core.container import (
    health_service,
    system_info_service,
)

router = APIRouter(
    prefix="/system",
    tags=["System"],
)


@router.get("/health")
async def system_health():

    return health_service.health()


@router.get("/info")
async def system_info():

    return system_info_service.info()