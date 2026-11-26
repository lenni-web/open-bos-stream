from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.config_apply import ConfigApplyError
from open_bos_stream.core.models import (
    AppConfig,
    MediaCaptureConfig,
    NotificationConfig,
    StorageConfig,
    SourceConfig,
)

from open_bos_stream.core.container import (
    config_apply_service,
    server_event_log,
)
from open_bos_stream.auth.roles import ADMIN, SUPERADMIN

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
    result = await apply_config(config)
    _log_change("Konfiguration gespeichert und aktiviert", request)
    return result


@router.put("/sources")
async def save_sources(sources: list[SourceConfig], request: Request):
    # Admins bearbeiten nur die Quellen. Alle ausschließlich für Superadmins
    # bestimmten Konfigurationsbereiche stammen unverändert vom Server.
    current = loader.load().model_dump()
    current["sources"] = [source.model_dump() for source in sources]
    candidate = AppConfig.model_validate(current)
    result = await apply_config(candidate)
    _log_change("Quellen gespeichert und aktiviert", request)
    return result


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


@router.post("/test")
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
