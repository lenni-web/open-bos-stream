from fastapi import APIRouter

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.models import AppConfig

from open_bos_stream.core.container import (
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

    print("===== CONFIG RECEIVED =====")
    print(config.model_dump())
    print("===========================")

    loader.save(config)

    #
    # Laufende Konfiguration übernehmen
    #

    stream_output_manager.reload(
        config
    )

    return {
        "success": True,
        "message": "Konfiguration gespeichert.",
    }
