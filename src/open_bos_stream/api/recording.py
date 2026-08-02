"""
Recording API
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from open_bos_stream.core.container import (
    recording_library,
    recording_service,
)
from open_bos_stream.recording.playback import (
    PlaybackPreparationError,
    RecordingPlaybackCache,
)

router = APIRouter(
    prefix="/recording",
    tags=["Recording"],
)
playback_cache = RecordingPlaybackCache(recording_library.directory)


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


@router.get("/play-compatible/{filename}")
async def play_compatible(filename: str):
    """Liefert eine vollständig abgeschlossene, browserkompatible MP4-Datei."""

    file = recording_library.get_file(filename)
    if file is None:
        raise HTTPException(
            status_code=404,
            detail="Aufnahme nicht gefunden.",
        )

    try:
        compatible = await run_in_threadpool(playback_cache.prepare, file)
    except PlaybackPreparationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Aufnahme konnte nicht aufbereitet werden: {exc}",
        ) from exc

    return FileResponse(
        path=compatible,
        media_type="video/mp4",
        filename=None,
    )


@router.delete("/{filename}")
async def delete(filename: str):
    file = recording_library.get_file(filename)
    success = recording_library.delete(filename)

    if success and file is not None:
        await run_in_threadpool(playback_cache.remove, file)

    return {
        "success": success,
    }
