"""
Media API
"""

from fastapi import APIRouter

from open_bos_stream.core.container import (
    media_library,
)
from open_bos_stream.auth.roles import SUPERADMIN

router = APIRouter(
    dependencies=[SUPERADMIN],
    prefix="/media",
    tags=["Media"],
)


@router.get("/files")
async def files():

    return media_library.list()
