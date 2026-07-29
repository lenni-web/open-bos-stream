"""
Recording API
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from open_bos_stream.core.container import (
    recording_library,
    recording_service,
)

router = APIRouter(
    prefix="/recording",
    tags=["Recording"],
)


@router.get("/status")
async def status():

    return recording_service.status


@router.post("/start")
async def start():

    try:

        recording_service.start()

        return {
            "success": True,
            "filename": recording_service.status.filename,
            "status": recording_service.status,
        }

    except RuntimeError as exc:

        return {
            "success": False,
            "error": str(exc),
        }


@router.post("/stop")
async def stop():

    try:

        recording_service.stop()

        return {
            "success": True,
            "status": recording_service.status,
        }

    except RuntimeError as exc:

        return {
            "success": False,
            "error": str(exc),
        }


@router.get("/files")
async def files():

    return recording_library.list()


@router.get("/download/{filename}")
async def download(filename: str):

    file = recording_library.get_file(filename)

    if file is None:
        raise HTTPException(
            status_code=404,
            detail="Aufnahme nicht gefunden.",
        )

    return FileResponse(
        path=file,
        filename=file.name,
        media_type="video/mp4",
    )


@router.get("/play/{filename}")
async def play(filename: str):

    file = recording_library.get_file(filename)

    if file is None:
        raise HTTPException(
            status_code=404,
            detail="Aufnahme nicht gefunden.",
        )

    return FileResponse(
        path=file,
        media_type="video/mp4",
    )


@router.delete("/{filename}")
async def delete(filename: str):

    success = recording_library.delete(filename)

    return {
        "success": success,
    }
