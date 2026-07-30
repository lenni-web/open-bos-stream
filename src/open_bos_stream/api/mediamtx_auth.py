"""Interne, pfadgebundene Publisher-Authentifizierung für MediaMTX."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.installation import installation_profile

router = APIRouter(
    prefix="/internal/mediamtx",
    tags=["MediaMTX"],
)


class MediaMTXAuthRequest(BaseModel):
    user: str = ""
    password: str = ""
    token: str = ""
    ip: str = ""
    action: str
    path: str = ""
    protocol: str = ""
    id: str = ""
    query: str = ""
    userAgent: str = ""


@router.post("/auth", include_in_schema=False)
async def authorize_mediamtx(
    payload: MediaMTXAuthRequest,
    request: Request,
) -> dict[str, bool]:
    """Schützt externe RTMP-Publisher im Serverprofil."""

    if installation_profile() != "server":
        return {"authorized": True}

    if payload.action != "publish":
        return {"authorized": True}

    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    publisher_ip = payload.ip.split("%", 1)[0]
    if publisher_ip in {"127.0.0.1", "::1"}:
        # Interne FFmpeg-Relays publizieren abgeleitete Viewer-Pfade.
        return {"authorized": True}

    if payload.protocol != "rtmp":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    source = next(
        (
            item
            for item in ConfigLoader().load().sources
            if item.enabled
            and item.type == "rtmp"
            and item.publish_path == payload.path.strip("/")
        ),
        None,
    )
    if source is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    if not secrets.compare_digest(
        payload.token,
        source.publish_token or "",
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    return {"authorized": True}
