"""Interne, pfadgebundene Publisher-Authentifizierung für MediaMTX."""

from __future__ import annotations

import logging
import secrets
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from open_bos_stream.core.container import config

logger = logging.getLogger(__name__)

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


def _publisher_credentials(
    payload: MediaMTXAuthRequest,
) -> tuple[str, str]:
    """Normalisiert Pfad und Token verschiedener MediaMTX-Versionen."""

    path, separator, path_query = payload.path.strip("/").partition("?")
    query_parts = [payload.query.lstrip("?")]
    if separator:
        query_parts.append(path_query)
    query = "&".join(part for part in query_parts if part)
    query_token = parse_qs(query).get("token", [""])[0]
    return path, payload.token or query_token


@router.post("/auth", include_in_schema=False)
async def authorize_mediamtx(
    payload: MediaMTXAuthRequest,
    request: Request,
) -> dict[str, bool]:
    """Schützt externe RTMP-Publisher in allen Installationsprofilen."""

    if payload.action != "publish":
        return {"authorized": True}

    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1"}:
        logger.warning(
            "MediaMTX-Authentifizierung von nicht-lokaler Adresse abgelehnt"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    publisher_ip = payload.ip.split("%", 1)[0]
    if publisher_ip in {"127.0.0.1", "::1"}:
        # Interne FFmpeg-Relays publizieren abgeleitete Viewer-Pfade.
        return {"authorized": True}

    if payload.protocol != "rtmp":
        logger.warning(
            "Publisher abgelehnt: Protokoll %s ist nicht RTMP",
            payload.protocol or "unbekannt",
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    publish_path, publish_token = _publisher_credentials(payload)
    source = next(
        (
            item
            for item in config.sources
            if item.enabled
            and item.type == "rtmp"
            and item.publish_path == publish_path
        ),
        None,
    )
    if source is None:
        logger.warning(
            "RTMP-Publisher für unbekannten oder deaktivierten Pfad %r "
            "abgelehnt",
            publish_path,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    if not secrets.compare_digest(
        publish_token,
        source.publish_token or "",
    ):
        logger.warning(
            "RTMP-Publisher für Pfad %r abgelehnt: Token vorhanden=%s",
            publish_path,
            bool(publish_token),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    return {"authorized": True}
