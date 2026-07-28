"""
Open BOS Stream
Application Entry Point
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from open_bos_stream.version import VERSION

from open_bos_stream.core.container import stream_service
from open_bos_stream.api.input import (
    router as input_router,
)
from open_bos_stream.api.encoder import (
    router as encoder_router,
)
from open_bos_stream.api.video_devices import (
    router as video_devices_router,
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
from open_bos_stream.logging.logger import setup_logging
import logging

setup_logging()
logger = logging.getLogger(__name__)


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

    yield

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
app.include_router(map_router)
