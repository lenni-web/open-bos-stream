"""
Recording API
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from open_bos_stream.core.container import (
    config,
    playback_cache,
    recording_library,
    recording_service,
    server_event_log,
)
from open_bos_stream.recording.playback import PlaybackPreparationError
from open_bos_stream.auth.media_access import (
    media_organization,
    require_media_access,
    visible_media,
)
from open_bos_stream.auth.roles import OPERATOR, SUPERADMIN

# Aufnahmesteuerung bleibt Superadmins vorbehalten; das Archiv sehen
# Drohnenteams für die Drohnen ihrer Wehr (auth/media_access.py).
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/recording",
    tags=["Recording"],
)


class ProtectionRequest(BaseModel):
    protected: bool


def _status(source_id: str):
    return next(
        (
            item for item in recording_service.statuses()
            if item.source_id == source_id
        ),
        None,
    )


async def _control(action, source_id: str, request: Request) -> dict:
    try:
        # Das Öffnen des Hauptstreams kann einige Sekunden dauern und darf
        # die übrigen Anfragen nicht blockieren.
        await run_in_threadpool(
            lambda: action(
                source_id=source_id,
                actor=request.state.user["username"],
            )
        )
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}
    return {"success": True, "status": _status(source_id)}


@router.post("/sources/{source_id}/start", dependencies=[SUPERADMIN])
async def start(source_id: str, request: Request):
    return await _control(recording_service.start, source_id, request)


@router.post("/sources/{source_id}/stop", dependencies=[SUPERADMIN])
async def stop(source_id: str, request: Request):
    return await _control(recording_service.stop, source_id, request)


@router.get("/files", dependencies=[OPERATOR])
async def files(request: Request):

    return visible_media(request.state.user, recording_library.list(), config)


@router.get("/download/{filename}", dependencies=[OPERATOR])
async def download(filename: str, request: Request):
    require_media_access(request.state.user, filename, config)

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


@router.get("/play/{filename}", dependencies=[OPERATOR])
async def play(filename: str, request: Request):
    require_media_access(request.state.user, filename, config)

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


@router.get("/play-compatible/{filename}", dependencies=[OPERATOR])
async def play_compatible(filename: str, request: Request):
    require_media_access(request.state.user, filename, config)
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
        # FFmpeg-Ausgabe enthält Serverpfade: nur ins Protokoll.
        logger.warning("Aufnahme %s nicht aufbereitet: %s", file.name, exc)
        raise HTTPException(
            status_code=422,
            detail=(
                "Die Aufnahme konnte für den Browser nicht aufbereitet werden. "
                "Bitte herunterladen und lokal abspielen."
            ),
        ) from exc

    return FileResponse(
        path=compatible,
        media_type="video/mp4",
        filename=None,
    )


@router.delete("/{filename}", dependencies=[OPERATOR])
async def delete(filename: str, request: Request):
    require_media_access(request.state.user, filename, config, level="admin")
    file = recording_library.get_file(filename)
    success = recording_library.delete(filename)
    if success:
        server_event_log.record(
            "warning",
            f"🗑 Aufnahme gelöscht · {filename}",
            actor=request.state.user["username"],
            organization_id=media_organization(filename, config),
        )

    if success and file is not None:
        await run_in_threadpool(playback_cache.remove, file)

    return {
        "success": success,
    }


@router.put("/{filename}/protected", dependencies=[OPERATOR])
async def set_protected(filename: str, request: ProtectionRequest, http: Request):
    """Aufnahme vor automatischer Bereinigung schützen oder freigeben."""

    require_media_access(http.state.user, filename, config)

    if not recording_library.set_protected(filename, request.protected):
        raise HTTPException(
            status_code=404,
            detail="Aufnahme nicht gefunden.",
        )

    return {
        "success": True,
        "protected": request.protected,
    }
