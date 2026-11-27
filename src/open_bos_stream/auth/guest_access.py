"""Welche Quellen und Livebilder ein Zugang sehen darf.

* Gäste: nur die Quellen ihres Gastlinks.
* Konten: Quellen der Organisationen, in denen sie eine Rolle haben
  (inklusive Unterbaum), dazu Quellen ohne Zuordnung.
* Superadmin und das lokale Display: alles.
"""

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


def is_restricted(user: dict | None) -> bool:
    """Gilt für diesen Zugang eine Einschränkung auf Organisationen?"""

    if not user:
        return True
    if is_guest(user):
        return True
    return "org_view" in user and not user.get("platform_admin")


def can_see_source(user: dict | None, source: SourceConfig) -> bool:
    if is_guest(user):
        return source.id in set(user.get("source_ids") or [])
    if not is_restricted(user):
        return True
    return (
        source.organization_id is None
        or source.organization_id in set(user.get("org_view") or [])
        # Drohnen anderer Wehren, solange ein gemeinsamer Einsatz läuft.
        or source.id in set(user.get("incident_source_ids") or [])
    )


def can_operate_source(user: dict | None, source: SourceConfig) -> bool:
    if is_guest(user) or not user:
        return False
    if not is_restricted(user) or user.get("server_admin"):
        return True
    # Quellen ohne Wehr sind für alle sichtbar, bedienen (Aufnahmen,
    # Gastlinks, Einsätze) dürfen sie aber nur Kreis-Admins und Superadmins.
    return source.organization_id in set(user.get("org_operate") or [])


def can_admin_source(user: dict | None, source: SourceConfig) -> bool:
    if is_guest(user) or not user:
        return False
    if not is_restricted(user) or user.get("server_admin"):
        return True
    return source.organization_id in set(user.get("org_admin") or [])


def visible_sources(user: dict | None, config: AppConfig) -> list[SourceConfig]:
    return [source for source in config.sources if can_see_source(user, source)]


def visible_source_ids(user: dict | None, config: AppConfig) -> set[str] | None:
    """Sichtbare Quellen; None bedeutet: keine Einschränkung."""

    if not is_restricted(user):
        return None
    return {source.id for source in visible_sources(user, config)}


def source_paths(sources) -> set[str]:
    paths: set[str] = set()
    for source in sources:
        paths.update(
            {
                source.viewer_path,
                source.fullscreen_viewer_path,
                source.publish_path,
            }
        )
    return paths


def allowed_media_paths(user: dict | None, config: AppConfig) -> set[str] | None:
    """MediaMTX-Pfade, die dieser Zugang abrufen darf (None: alle)."""

    if not is_restricted(user):
        return None
    return source_paths(visible_sources(user, config))


def require_source_access(user: dict | None, source_id: str, config: AppConfig) -> None:
    if is_guest(user):
        require_guest_source(user, source_id)
        return
    source = next((item for item in config.sources if item.id == source_id), None)
    if source is not None and not can_see_source(user, source):
        raise HTTPException(
            status_code=403,
            detail="Diese Quelle gehört zu einer anderen Organisation.",
        )


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
