"""
Open BOS Stream
Application Entry Point
"""

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from open_bos_stream.version import VERSION

from open_bos_stream.core.container import stream_service
from open_bos_stream.core.container import auth_service
from open_bos_stream.core.container import fullscreen_relay_manager
from open_bos_stream.core.container import recording_service
from open_bos_stream.core.container import media_storage_service
from open_bos_stream.auth.middleware import AuthMiddleware
from open_bos_stream.api.auth import router as auth_router
from open_bos_stream.api.input import (
    router as input_router,
)
from open_bos_stream.api.encoder import (
    router as encoder_router,
)
from open_bos_stream.api.video_devices import (
    router as video_devices_router,
)
from open_bos_stream.api.display import (
    router as display_router,
)
from open_bos_stream.api.web_access import (
    router as web_access_router,
)
from open_bos_stream.api.map import (
    router as map_router,
)
from open_bos_stream.api.stream import router as stream_router
from open_bos_stream.api.web import router as web_router
from open_bos_stream.api.system import router as system_router
from open_bos_stream.api.dashboard import router as dashboard_router
from open_bos_stream.api.config import router as config_router
from open_bos_stream.api.recording import router as recording_router
from open_bos_stream.api.snapshot import router as snapshot_router
from open_bos_stream.api.media import (
    router as media_router,
)
from open_bos_stream.api.stream_output import (
    router as stream_output_router,
)
from open_bos_stream.api.mediamtx_auth import (
    router as mediamtx_auth_router,
)
from open_bos_stream.logging.logger import setup_logging
import logging

setup_logging()
logger = logging.getLogger(__name__)


async def automatic_recording_loop() -> None:
    """Steuert automatische Aufnahmen unabhängig vom Browser."""

    while True:
        try:
            await asyncio.to_thread(recording_service.maintain)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Automatische Aufnahmesteuerung fehlgeschlagen.")
        await asyncio.sleep(1)


async def storage_protection_loop() -> None:
    """Überwacht den freien Speicher und bereinigt bei Bedarf."""

    while True:
        try:
            available = await asyncio.to_thread(
                media_storage_service.enforce
            )
            if not available and recording_service.status.recording:
                message = media_storage_service.blocked_message()
                logger.warning(
                    "Laufende Aufnahme wird wegen Speichermangel beendet."
                )
                await asyncio.to_thread(
                    recording_service.stop_for_storage,
                    message,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Speicherüberwachung fehlgeschlagen.")
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialisiert die Anwendung."""

    if stream_service.managed:
        try:
            if not stream_service.running:
                stream_service.start()
        except Exception:
            logger.exception(
                "Der interne Streamer konnte nicht gestartet werden."
            )

    recording_task = asyncio.create_task(automatic_recording_loop())
    storage_task = asyncio.create_task(storage_protection_loop())

    try:
        yield
    finally:
        for task in (recording_task, storage_task):
            task.cancel()
        for task in (recording_task, storage_task):
            with suppress(asyncio.CancelledError):
                await task

    if recording_service.status.recording:
        try:
            recording_service.stop(automatic=True)
        except Exception:
            logger.exception(
                "Die laufende Aufnahme konnte nicht sauber beendet werden."
            )

    fullscreen_relay_manager.close()

    if stream_service.managed:
        try:
            stream_service.stop()
        except Exception:
            logger.exception(
                "Der interne Streamer konnte nicht gestoppt werden."
            )


app = FastAPI(
    title="Open BOS Stream",
    version=VERSION,
    lifespan=lifespan,
)
app.add_middleware(AuthMiddleware, service=auth_service)

# ----------------------------------------------------------
# Static Files
# ----------------------------------------------------------

app.mount(
    "/static",
    StaticFiles(directory="src/open_bos_stream/static"),
    name="static",
)

# ----------------------------------------------------------
# Router
# ----------------------------------------------------------

app.include_router(web_router)
app.include_router(auth_router)
app.include_router(stream_router)
app.include_router(input_router)
app.include_router(system_router)
app.include_router(dashboard_router)
app.include_router(config_router)
app.include_router(recording_router)
app.include_router(snapshot_router)
app.include_router(media_router)
app.include_router(stream_output_router)
app.include_router(encoder_router)
app.include_router(video_devices_router)
app.include_router(display_router)
app.include_router(web_access_router)
app.include_router(map_router)
app.include_router(mediamtx_auth_router)
