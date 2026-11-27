"""
Snapshot API
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from open_bos_stream.core.container import (
    config,
    server_event_log,
    snapshot_library,
    snapshot_service,
)
from open_bos_stream.auth.media_access import (
    media_organization,
    require_media_access,
    visible_media,
)
from open_bos_stream.auth.roles import OPERATOR, SUPERADMIN

# Snapshot-Steuerung bleibt Superadmins vorbehalten; das Archiv sehen
# Drohnenteams für die Drohnen ihrer Wehr (auth/media_access.py).
router = APIRouter(
    prefix="/snapshot",
    tags=["Snapshot"],
)


class ProtectionRequest(BaseModel):
    protected: bool


@router.post("/sources/{source_id}", dependencies=[SUPERADMIN])
async def create(source_id: str, request: Request):
    """Neuen Snapshot einer Drohne erstellen."""

    try:
        filename = await run_in_threadpool(snapshot_service.create, source_id)
    except (RuntimeError, TimeoutError) as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "snapshot_creation_failed",
                "message": str(exc),
            },
        ) from exc

    server_event_log.record(
        "info",
        f"📸 Snapshot erstellt · {filename.name}",
        actor=request.state.user["username"],
    )
    return {
        "success": True,
        "filename": filename.name,
        "status": snapshot_service.status,
    }


@router.get("/files", dependencies=[OPERATOR])
async def files(request: Request):
    """Snapshots der Drohnen, die dieses Konto verwalten darf."""

    return visible_media(request.state.user, snapshot_library.list(), config)


@router.get("/download/{filename}", dependencies=[OPERATOR])
async def download(filename: str, request: Request):
    require_media_access(request.state.user, filename, config)
    """Snapshot herunterladen."""

    file = snapshot_library.get_file(filename)

    if file is None:
        return {
            "success": False,
            "error": "Datei nicht gefunden",
        }

    return FileResponse(
        path=file,
        filename=file.name,
        media_type="image/jpeg",
    )


@router.get("/view/{filename}", dependencies=[OPERATOR])
async def view(filename: str, request: Request):
    require_media_access(request.state.user, filename, config)
    """Snapshot anzeigen."""

    file = snapshot_library.get_file(filename)

    if file is None:
        return {
            "success": False,
            "error": "Datei nicht gefunden",
        }

    return FileResponse(
        path=file,
        media_type="image/jpeg",
    )


@router.delete("/{filename}", dependencies=[OPERATOR])
async def delete(filename: str, request: Request):
    """Snapshot löschen."""

    require_media_access(request.state.user, filename, config, level="admin")
    success = snapshot_library.delete(filename)
    if success:
        server_event_log.record(
            "warning",
            f"🗑 Snapshot gelöscht · {filename}",
            actor=request.state.user["username"],
            organization_id=media_organization(filename, config),
        )

    return {
        "success": success,
    }


@router.put("/{filename}/protected", dependencies=[OPERATOR])
async def set_protected(filename: str, request: ProtectionRequest, http: Request):
    """Snapshot vor automatischer Bereinigung schützen oder freigeben."""

    require_media_access(http.state.user, filename, config)

    if not snapshot_library.set_protected(filename, request.protected):
        raise HTTPException(
            status_code=404,
            detail="Snapshot nicht gefunden.",
        )

    return {
        "success": True,
        "protected": request.protected,
    }
