from fastapi import APIRouter

from open_bos_stream.core.container import (
    health_service,
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

    return health_service.health()


@router.get("/info")
async def system_info():

    info = system_info_service.info().model_dump()
    info["installation_profile"] = installation_profile()
    info["server_access"] = server_access_settings()
    return info
