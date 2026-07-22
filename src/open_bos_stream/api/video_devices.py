"""
Video Device API
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
)

from open_bos_stream.stream.inputs.device_manager import (
    DeviceManager,
)

router = APIRouter(

    prefix="/system",

    tags=["System"],

)


@router.get(
    "/video-devices",
)
async def video_devices():

    return DeviceManager.video_devices()