"""
Media API
"""

from fastapi import APIRouter, Request

from open_bos_stream.auth.media_access import visible_media
from open_bos_stream.auth.roles import OPERATOR
from open_bos_stream.core.container import (
    config,
    media_library,
)

router = APIRouter(
    dependencies=[OPERATOR],
    prefix="/media",
    tags=["Media"],
)


@router.get("/files")
async def files(request: Request):
    """Aufnahmen und Snapshots der Drohnen der eigenen Wehr(en)."""

    return visible_media(request.state.user, media_library.list(), config)
