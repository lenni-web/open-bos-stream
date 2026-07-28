from fastapi import APIRouter

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.models import AppConfig

from open_bos_stream.core.container import (
    config as runtime_config,
    stream_service,
    stream_output_manager,
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
    was_managed = stream_service.managed

    loader.save(config)

    if was_managed and config.passthrough_active:
        stream_service.stop()

    for field_name in AppConfig.model_fields:
        setattr(
            runtime_config,
            field_name,
            getattr(config, field_name),
        )

    stream_service.reload(runtime_config)
    stream_output_manager.reload(runtime_config)

    if runtime_config.passthrough_active:
        message = (
            "Konfiguration gespeichert; Passthrough wartet "
            "auf den externen Publisher."
        )
    else:
        stream_service.restart()
        message = (
            "Konfiguration gespeichert und Streamer neu gestartet."
        )

    return {
        "success": True,
        "message": message,
    }
