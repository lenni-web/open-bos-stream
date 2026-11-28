import ipaddress
import socket
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator
from starlette.concurrency import run_in_threadpool

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.config_apply import ConfigApplyError
from open_bos_stream.core.models import (
    AppConfig,
    MediaCaptureConfig,
    NotificationConfig,
    StorageConfig,
    SourceConfig,
    check_hidden_profiles,
)

from open_bos_stream.core.container import (
    config_apply_service,
    server_event_log,
)
from open_bos_stream.auth.guest_access import (
    can_admin_source,
    can_see_source,
    is_restricted,
)
from open_bos_stream.auth.roles import ADMIN, SUPERADMIN, SERVER_ADMIN

router = APIRouter(
    dependencies=[ADMIN],
    prefix="/config",
    tags=["Configuration"],
)

loader = ConfigLoader()


async def apply_config(config: AppConfig) -> dict:
    try:
        # systemctl und die anschließende Bereitschaftsprüfung sind blockierend.
        # Sie dürfen den FastAPI-Eventloop nicht anhalten.
        message = await run_in_threadpool(
            config_apply_service.apply,
            config,
        )
    except ConfigApplyError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "configuration_activation_failed",
                "message": str(exc),
            },
        ) from exc

    return {
        "success": True,
        "message": message,
    }


def _log_change(message: str, request: Request) -> None:
    server_event_log.record(
        "success",
        f"⚙️ {message}",
        actor=request.state.user["username"],
    )


def mask_url(url: str) -> str:
    """Ziel-URL ohne Pfad, Stream-Schlüssel und Zugangsdaten."""

    parts = urlsplit(url)
    if not parts.scheme or not parts.hostname:
        return "***"
    host = parts.hostname
    if parts.port:
        host = f"{host}:{parts.port}"
    return f"{parts.scheme}://{host}/***"


SECRET_FIELD_HINTS = ("token", "password", "secret", "key")


def strip_credentials(url: str | None) -> str | None:
    """Adresse ohne Benutzername und Passwort (Host und Pfad bleiben)."""

    if not url:
        return url
    parts = urlsplit(url)
    if parts.username is None and parts.password is None:
        return url
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return parts._replace(netloc=f"***@{host}").geturl()


def redacted_source(source: SourceConfig) -> SourceConfig:
    """Quelle einer anderen Wehr: sichtbar, aber ohne Sende-Schlüssel und
    Zugangsdaten. model_construct, damit kein neuer Schlüssel entsteht."""

    data = source.model_dump()
    for key in list(data):
        if any(hint in key.lower() for hint in SECRET_FIELD_HINTS):
            data[key] = None
    data["url"] = strip_credentials(data.get("url"))
    data["preview_url"] = strip_credentials(data.get("preview_url"))
    data["redacted"] = True
    return SourceConfig.model_construct(**data)


def visible_config_sources(user: dict, sources: list[SourceConfig]) -> list[SourceConfig]:
    """Eigene Quellen vollständig, fremde sichtbare Quellen ohne Geheimnisse."""

    return [
        source if can_admin_source(user, source) else redacted_source(source)
        for source in sources
        if can_see_source(user, source)
    ]


@router.get("/")
async def get_config(request: Request):
    config = loader.load()
    if request.state.user["role"] != "superadmin":
        # Admins dürfen Streaming-Ausgänge weder sehen noch ändern; ihre
        # Ziel-URLs enthalten in der Regel geheime Stream-Schlüssel.
        for output in config.stream_outputs:
            output.url = mask_url(output.url)
        # Mailserver und Empfängeradressen sind nur für Superadmins.
        config.notifications = NotificationConfig.model_construct(
            enabled=config.notifications.enabled,
        )
    user = request.state.user
    if is_restricted(user) and not user.get("server_admin"):
        # Wehr-Admins sehen nur Quellen ihrer Organisationen (und solche
        # ohne Zuordnung); bearbeiten dürfen sie nur ihre eigenen.
        # Fremde Quellen (z. B. Drohnen anderer Wehren im gemeinsamen
        # Einsatz) ohne Sende-Schlüssel und Zugangsdaten ausliefern.
        config.sources = visible_config_sources(user, config.sources)
        # Ältere RTMP-Eingänge (vor den Quellen) enthalten Sende-Schlüssel.
        config.rtmp_inputs = []
    return config


@router.put("/", dependencies=[SUPERADMIN])
async def save_config(config: AppConfig, request: Request):
    # Admins speichern ausschließlich über PUT /config/sources.
    # Benachrichtigungen haben einen eigenen Endpunkt; ein veralteter Stand
    # aus dem Browser darf sie hier nicht überschreiben.
    stored = loader.load()
    config.notifications = stored.notifications
    # Wetter ebenfalls nur über den eigenen Endpunkt.
    config.weather = stored.weather
    config.hidden_source_profiles = stored.hidden_source_profiles
    result = await apply_config(config)
    _log_change("Konfiguration gespeichert und aktiviert", request)
    return result


@router.put("/sources")
async def save_sources(sources: list[SourceConfig], request: Request):
    # Admins bearbeiten nur die Quellen. Alle ausschließlich für Superadmins
    # bestimmten Konfigurationsbereiche stammen unverändert vom Server.
    stored = loader.load()
    current = stored.model_dump()
    current["sources"] = [
        source.model_dump()
        for source in merge_sources(
            request.state.user,
            stored.sources,
            sources,
            hidden_profiles=stored.hidden_source_profiles,
        )
    ]
    try:
        candidate = AppConfig.model_validate(current)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = await apply_config(candidate)
    _log_change("Drohnen gespeichert und aktiviert", request)
    return result


# Quellen, die der Server selbst abruft (nicht nur empfängt).
OUTBOUND_SOURCE_TYPES = {"rtsp", "http", "hls"}


def _internal_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    return (
        ip.is_loopback or ip.is_private or ip.is_link_local
        or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


def fetches_internal_address(source: SourceConfig) -> bool:
    """Würde der Server eine Adresse im eigenen bzw. internen Netz abrufen?

    Schutz gegen Anfragen an interne Dienste (z. B. die MediaMTX-API) über
    eine von Wehr-Admins eingetragene Drohne.
    """

    if source.type not in OUTBOUND_SOURCE_TYPES:
        return False
    for url in (source.url, source.preview_url):
        if not url:
            continue
        host = (urlsplit(url).hostname or "").strip("[]").lower()
        if not host or host == "localhost" or host.endswith(".localhost"):
            return True
        if _internal_ip(host):
            return True
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, None)}
        except OSError:
            # Nicht auflösbar: FFmpeg erreicht die Quelle ohnehin nicht.
            continue
        if any(_internal_ip(address) for address in addresses):
            return True
    return False


def merge_sources(
    user: dict,
    stored: list[SourceConfig],
    incoming: list[SourceConfig],
    hidden_profiles: list[str] | None = None,
) -> list[SourceConfig]:
    """Quellen aus dem Browser mit dem Serverstand zusammenführen.

    Kreis-Admins und Superadmins ersetzen die Liste. Wehr-Admins ändern nur
    Drohnen ihrer Organisationen; alle übrigen bleiben unverändert.
    """

    if not is_restricted(user) or user.get("server_admin"):
        return list(incoming)
    stored_by_id = {source.id: source for source in stored}
    incoming_by_id = {}
    for source in incoming:
        existing = stored_by_id.get(source.id)
        if existing is not None and not can_admin_source(user, existing):
            if can_see_source(user, existing):
                # Nur sichtbar, nicht verwaltbar: Serverstand behalten.
                continue
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Die ID „{source.id}“ ist bereits an eine Drohne einer "
                    "anderen Organisation vergeben. Bitte eine andere ID wählen."
                ),
            )
        if not can_admin_source(user, source):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Drohne „{source.name}“: Bitte eine Organisation wählen, "
                    "in der Sie Wehr-Admin sind."
                ),
            )
        # Versteckte Profile lassen sich nicht neu wählen; bestehende
        # Drohnen behalten ihr Profil.
        if (
            source.type == "rtmp"
            and source.profile in (hidden_profiles or [])
            and (
                existing is None
                or (existing.type, existing.profile) != (source.type, source.profile)
            )
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Drohne „{source.name}“: Dieses Empfangsprofil ist nicht "
                    "freigegeben. Bitte ein anderes wählen."
                ),
            )
        changed = existing is None or (existing.url, existing.preview_url) != (source.url, source.preview_url)
        if changed and fetches_internal_address(source):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Drohne „{source.name}“: Adressen im internen Netz des "
                    "Servers (localhost, private Netze) richtet nur ein "
                    "Kreis-Admin ein."
                ),
            )
        incoming_by_id[source.id] = source
    merged = []
    for source in stored:
        if not can_admin_source(user, source):
            merged.append(source)
        elif source.id in incoming_by_id:
            merged.append(incoming_by_id.pop(source.id))
    merged.extend(incoming_by_id.values())
    return merged


class SourceProfileRelease(BaseModel):
    hidden: list[str]

    @field_validator("hidden")
    @classmethod
    def validate_hidden(cls, value: list[str]) -> list[str]:
        return check_hidden_profiles(value)


@router.put("/source-profiles", dependencies=[SUPERADMIN])
async def save_source_profiles(release: SourceProfileRelease, request: Request):
    hidden = await run_in_threadpool(
        config_apply_service.update_hidden_source_profiles,
        release.hidden,
    )
    _log_change("Freigabe der Empfangsprofile gespeichert", request)
    return {
        "success": True,
        "message": "Empfangsprofile wurden gespeichert.",
        "hidden": hidden,
    }


@router.put("/media-capture", dependencies=[SUPERADMIN])
async def save_media_capture(
    media_capture: MediaCaptureConfig,
    request: Request,
):
    saved = await run_in_threadpool(
        config_apply_service.update_media_capture,
        media_capture,
    )
    names = {source.id: source.name for source in loader.load().sources}
    automatic = ", ".join(
        names.get(item, item) for item in saved.automatic_source_ids
    ) or "keine"
    _log_change(f"Aufnahmesteuerung gespeichert (automatisch: {automatic})", request)
    return {
        "success": True,
        "message": "Aufnahmesteuerung wurde gespeichert.",
        "media_capture": saved,
    }


@router.put("/storage", dependencies=[SUPERADMIN])
async def save_storage(
    storage: StorageConfig,
    request: Request,
):
    saved = await run_in_threadpool(
        config_apply_service.update_storage,
        storage,
    )
    _log_change("Speicherschutz gespeichert", request)
    return {
        "success": True,
        "message": "Speicherschutz wurde gespeichert.",
        "storage": saved,
    }


@router.post("/test", dependencies=[SERVER_ADMIN])
async def test_config(config: AppConfig):
    try:
        checks = await run_in_threadpool(
            config_apply_service.test,
            config,
        )
    except ConfigApplyError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "configuration_test_failed",
                "message": str(exc),
            },
        ) from exc

    return {
        "success": True,
        "message": (
            f"Konfiguration ist aktivierbar "
            f"({len(checks)} Prüfungen)."
        ),
        "checks": checks,
    }


@router.post("/restore", dependencies=[SUPERADMIN])
async def restore_config(request: Request):
    try:
        message = await run_in_threadpool(
            config_apply_service.restore_last_known_good
        )
    except ConfigApplyError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "configuration_restore_failed",
                "message": str(exc),
            },
        ) from exc

    _log_change("Letzte funktionierende Konfiguration geladen", request)
    return {"success": True, "message": message}
