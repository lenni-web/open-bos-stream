"""Interne, pfadgebundene Publisher-Authentifizierung für MediaMTX."""

from __future__ import annotations

import logging
import secrets
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, field_validator

from open_bos_stream.core.container import auth_service, config
from open_bos_stream.auth.guest_access import guest_paths, is_guest
from open_bos_stream.auth.roles import PUBLIC

logger = logging.getLogger(__name__)

LOOPBACK_ADDRESSES = {"127.0.0.1", "::1"}
BROWSER_READ_PROTOCOLS = {"webrtc", "hls"}
PUBLISH_PROTOCOLS = {"rtmp", "srt"}

router = APIRouter(
    dependencies=[PUBLIC],
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

    @field_validator("*", mode="before")
    @classmethod
    def _null_as_empty(cls, value):
        # MediaMTX sendet z. B. "id": null, wenn noch keine Sitzung besteht
        # (HLS-Startseite, WHEP-OPTIONS). Ohne diese Umwandlung lehnt die
        # Validierung die Anfrage mit 422 ab und der Leser wird abgewiesen.
        return "" if value is None else value


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
    """Schützt Publisher und Leser von MediaMTX in allen Profilen."""

    if payload.action not in {"publish", "read"}:
        return {"authorized": True}

    client_host = request.client.host if request.client else ""
    if client_host not in LOOPBACK_ADDRESSES:
        logger.warning(
            "MediaMTX-Authentifizierung von nicht-lokaler Adresse abgelehnt"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    if payload.action == "read":
        return _authorize_reader(payload)

    publisher_ip = payload.ip.split("%", 1)[0]
    if publisher_ip in LOOPBACK_ADDRESSES:
        # Interne FFmpeg-Relays publizieren abgeleitete Viewer-Pfade.
        return {"authorized": True}

    if payload.protocol not in PUBLISH_PROTOCOLS:
        logger.warning(
            "Publisher abgelehnt: Protokoll %s ist nicht RTMP oder SRT",
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
            and item.ingest_protocol == payload.protocol
            and item.publish_path == publish_path
        ),
        None,
    )
    if source is None:
        logger.warning(
            "%s-Publisher für unbekannten oder deaktivierten Pfad %r "
            "abgelehnt",
            payload.protocol.upper(),
            publish_path,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    if not secrets.compare_digest(
        publish_token,
        source.publish_token or "",
    ):
        logger.warning(
            "%s-Publisher für Pfad %r abgelehnt: Token vorhanden=%s",
            payload.protocol.upper(),
            publish_path,
            bool(publish_token),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    return {"authorized": True}


def _authorize_reader(payload: MediaMTXAuthRequest) -> dict[str, bool]:
    """Lesen nur lokal oder mit gültigem Medien-Token aus der Sitzung.

    Lokale Leser sind Caddy (nach Prüfung der Open-BOS-Sitzung), die
    internen FFmpeg-Prozesse und das Kiosk-Display. Browser, die MediaMTX
    ohne Caddy direkt abrufen, legen ein Medien-Token aus /auth/media-token
    vor. RTMP-, RTSP- und SRT-Leser von außen werden immer abgelehnt.
    """

    reader_ip = payload.ip.split("%", 1)[0]
    if reader_ip in LOOPBACK_ADDRESSES:
        return {"authorized": True}

    path, token = _publisher_credentials(payload)
    user = (
        auth_service.verify_token(token, purpose="media")
        if payload.protocol in BROWSER_READ_PROTOCOLS
        else None
    )
    if user is not None and (
        not is_guest(user) or path in guest_paths(user, config)
    ):
        return {"authorized": True}

    logger.warning(
        "Leser für Pfad %r abgelehnt (Protokoll %s, Adresse %s, "
        "Token vorhanden=%s)",
        payload.path.strip("/").partition("?")[0],
        payload.protocol or "unbekannt",
        reader_ip or "unbekannt",
        bool(token),
    )
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
