"""API zur manuellen Steuerung des lokalen Displays."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.container import (
    config as runtime_config,
    display_manager,
)
from open_bos_stream.display.config import DisplayConfig


router = APIRouter(
    prefix="/display",
    tags=["Display"],
)
loader = ConfigLoader()


@router.get("/status")
async def display_status():
    return display_manager.status()


@router.get("/config")
async def get_display_config():
    return runtime_config.display


@router.put("/config")
async def save_display_config(config: DisplayConfig):
    previous = runtime_config.display.model_copy(deep=True)

    try:
        complete_config = loader.load()
        complete_config.display = config
        loader.save(complete_config)

        runtime_config.display = config
        display_manager.reload(config)

        if config.enabled:
            if display_manager.running:
                activated = display_manager.restart()
            else:
                activated = display_manager.start()

            if not activated:
                raise RuntimeError(
                    "Display-Dienst wurde nicht aktiv."
                )
        elif display_manager.running:
            display_manager.stop()

    except Exception as exc:
        complete_config = loader.load()
        complete_config.display = previous
        loader.save(complete_config)
        runtime_config.display = previous
        display_manager.reload(previous)

        try:
            if previous.enabled:
                display_manager.restart()
            elif display_manager.running:
                display_manager.stop()
        except Exception:
            pass

        raise HTTPException(
            status_code=409,
            detail={
                "code": "display_activation_failed",
                "message": str(exc),
            },
        ) from exc

    return {
        "success": True,
        "message": (
            "Display gestartet."
            if config.enabled
            else "Display beendet."
        ),
        "status": display_manager.status(),
    }
