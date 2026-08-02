"""
Recording API
"""

from __future__ import annotations

import subprocess

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

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


@router.get("/play-compatible/{filename}")
async def play_compatible(filename: str):
    """Transkodiert ältere oder browserfremde Aufnahmen beim Abspielen."""

    file = recording_library.get_file(filename)
    if file is None:
        raise HTTPException(
            status_code=404,
            detail="Aufnahme nicht gefunden.",
        )

    def stream():
        process = subprocess.Popen(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error",
                "-nostdin",
                "-i", str(file),
                "-map", "0:v:0",
                "-map", "0:a:0?",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-movflags", "frag_keyframe+empty_moov+default_base_moof",
                "-f", "mp4",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        try:
            assert process.stdout is not None
            while chunk := process.stdout.read(64 * 1024):
                yield chunk
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()

    return StreamingResponse(
        stream(),
        media_type="video/mp4",
        headers={"Cache-Control": "no-store"},
    )


@router.delete("/{filename}")
async def delete(filename: str):

    success = recording_library.delete(filename)

    return {
        "success": success,
    }
