from fastapi import APIRouter, HTTPException

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.config_apply import ConfigApplyError
from open_bos_stream.core.models import AppConfig

from open_bos_stream.core.container import (
    config_apply_service,
)

router = APIRouter(
    prefix="/config",
    tags=["Configuration"],
)

loader = ConfigLoader()


@router.get("/")
async def get_config():

    return loader.load()


@router.put("/")
async def save_config(config: AppConfig):
    try:
        message = config_apply_service.apply(config)
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


@router.post("/test")
async def test_config(config: AppConfig):
    try:
        checks = config_apply_service.test(config)
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
        message = config_apply_service.restore_last_known_good()
    except ConfigApplyError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "configuration_restore_failed",
                "message": str(exc),
            },
        ) from exc

    return {"success": True, "message": message}
