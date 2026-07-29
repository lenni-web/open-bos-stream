"""API für den optionalen Webzugriff über Port 80."""

from fastapi import APIRouter, HTTPException

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.container import (
    config as runtime_config,
    web_access_manager,
)
from open_bos_stream.web_access.config import WebAccessConfig


router = APIRouter(prefix="/web-access", tags=["Webzugriff"])
loader = ConfigLoader()


@router.get("/status")
async def web_access_status():
    return web_access_manager.status()


@router.get("/config")
async def get_web_access_config():
    return runtime_config.web_access


@router.put("/config")
async def save_web_access_config(config: WebAccessConfig):
    try:
        complete_config = loader.load()
        complete_config.web_access = config
        loader.save(complete_config)
        runtime_config.web_access = config
        web_access_manager.reload(config)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "web_access_save_failed",
                "message": f"Konfiguration konnte nicht gespeichert werden: {exc}",
            },
        ) from exc

    try:
        if config.enabled:
            if not web_access_manager.start():
                raise RuntimeError("Standard-Webzugriff wurde nicht aktiv.")
        elif web_access_manager.running:
            web_access_manager.stop()
    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "web_access_activation_failed",
                "message": (
                    f"{exc} Die Einstellung wurde gespeichert; "
                    "Port 8000 bleibt erreichbar."
                ),
            },
        ) from exc

    return {
        "success": True,
        "message": (
            "Standard-Webzugriff über Port 80 aktiviert."
            if config.enabled
            else "Standard-Webzugriff deaktiviert."
        ),
        "status": web_access_manager.status(),
    }
