"""Was ein Gast sehen darf: nur die Quellen seines Gastlinks."""

from __future__ import annotations

from fastapi import HTTPException

from open_bos_stream.core.models import AppConfig, SourceConfig


def is_guest(user: dict | None) -> bool:
    return bool(user) and user.get("role") == "guest"


def guest_sources(user: dict, config: AppConfig) -> list[SourceConfig]:
    allowed = set(user.get("source_ids") or [])
    return [
        source
        for source in config.sources
        if source.enabled and source.id in allowed
    ]


def guest_paths(user: dict, config: AppConfig) -> set[str]:
    """MediaMTX-Pfade (Vorschau und Vollbild) der freigegebenen Quellen."""

    paths: set[str] = set()
    for source in guest_sources(user, config):
        paths.update(
            {
                source.viewer_path,
                source.fullscreen_viewer_path,
                source.publish_path,
            }
        )
    return paths


def media_uri_allowed(uri: str, paths: set[str]) -> bool:
    """Prüft eine von Caddy weitergereichte WHEP-/HLS-Adresse.

    Je nach Caddy-Konfiguration enthält die Adresse das Präfix /whep bzw.
    /hls oder schon den gekürzten Pfad. Entscheidend ist, dass der
    angefragte Stream zu den freigegebenen Pfaden gehört.
    """

    path = uri.split("?", 1)[0]
    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return False
    if segments[0] in {"whep", "hls"} and len(segments) > 1:
        return segments[1] in paths
    return segments[0] in paths


def require_guest_source(user: dict | None, source_id: str) -> None:
    if is_guest(user) and source_id not in set(user.get("source_ids") or []):
        raise HTTPException(
            status_code=403,
            detail="Diese Quelle ist für den Gastzugang nicht freigegeben.",
        )
