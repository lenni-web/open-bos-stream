"""
Snapshot API
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from open_bos_stream.core.container import (
    snapshot_library,
    snapshot_service,
)

router = APIRouter(
    prefix="/snapshot",
    tags=["Snapshot"],
)


@router.get("/status")
async def status():
    """Aktuellen Snapshot-Status."""

    return snapshot_service.status


@router.post("/create")
async def create():
    """Neuen Snapshot erstellen."""

    try:
        filename = snapshot_service.create()
    except (RuntimeError, TimeoutError) as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "snapshot_creation_failed",
                "message": str(exc),
            },
        ) from exc

    return {
        "success": True,
        "filename": filename.name,
        "status": snapshot_service.status,
    }


@router.get("/files")
async def files():
    """Liste aller Snapshots."""

    return snapshot_library.list()


@router.get("/download/{filename}")
async def download(filename: str):
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


@router.get("/view/{filename}")
async def view(filename: str):
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


@router.delete("/{filename}")
async def delete(filename: str):
    """Snapshot löschen."""

    success = snapshot_library.delete(filename)

    return {
        "success": success,
    }
