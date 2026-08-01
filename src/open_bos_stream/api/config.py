from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.config_apply import ConfigApplyError
from open_bos_stream.core.models import AppConfig, SourceConfig

from open_bos_stream.core.container import (
    config_apply_service,
)

router = APIRouter(
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


@router.get("/")
async def get_config(request: Request):
    if request.state.user["role"] == "viewer":
        raise HTTPException(
            status_code=403,
            detail="Für die Konfiguration ist die Rolle Admin erforderlich.",
        )

    return loader.load()


@router.put("/")
async def save_config(config: AppConfig, request: Request):
    if request.state.user["role"] != "superadmin":
        current = loader.load()
        protected = (
            ("stream_outputs", config.stream_outputs, current.stream_outputs),
            ("display", config.display, current.display),
            ("web_access", config.web_access, current.web_access),
            (
                "media_capture",
                config.media_capture,
                current.media_capture,
            ),
        )
        changed = [
            name
            for name, proposed, existing in protected
            if proposed != existing
        ]
        if changed:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "superadmin_configuration_required",
                    "message": (
                        "Nur Superadmins dürfen folgende Bereiche ändern: "
                        + ", ".join(changed)
                    ),
                },
            )
    return await apply_config(config)


@router.put("/sources")
async def save_sources(sources: list[SourceConfig], request: Request):
    if request.state.user["role"] == "viewer":
        raise HTTPException(
            status_code=403,
            detail="Für Quellenänderungen ist die Rolle Admin erforderlich.",
        )

    # Admins bearbeiten nur die Quellen. Alle ausschließlich für Superadmins
    # bestimmten Konfigurationsbereiche stammen unverändert vom Server.
    current = loader.load().model_dump()
    current["sources"] = [source.model_dump() for source in sources]
    candidate = AppConfig.model_validate(current)
    return await apply_config(candidate)


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


@router.post("/restore")
async def restore_config():
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

    return {"success": True, "message": message}
