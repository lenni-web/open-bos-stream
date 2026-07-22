"""
Media API
"""

from fastapi import APIRouter

from open_bos_stream.core.container import (
    media_library,
)

router = APIRouter(
    prefix="/media",
    tags=["Media"],
)


@router.get("/files")
async def files():

    return media_library.list()
