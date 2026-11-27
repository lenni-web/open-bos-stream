"""
Open BOS Drohnen
Application Entry Point
"""

import asyncio
import time
from contextlib import asynccontextmanager, suppress

# Vor allen anderen Modulen: Uhrzeiten in Mails, Dateinamen und Journal in
# deutscher Zeit statt der (oft UTC-)Systemzeit des Servers.
from open_bos_stream.core.timezone import apply_timezone

ACTIVE_TIMEZONE = apply_timezone()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from open_bos_stream.version import VERSION

from open_bos_stream.core.container import stream_service
from open_bos_stream.core.container import auth_service
from open_bos_stream.core.container import fullscreen_relay_manager
from open_bos_stream.core.container import recording_service
from open_bos_stream.core.container import media_storage_service
from open_bos_stream.core.container import dashboard_service
from open_bos_stream.core.container import notification_service
from open_bos_stream.core.container import push_service
from open_bos_stream.core.container import guest_link_store
from open_bos_stream.core.container import server_event_log
from open_bos_stream.core.container import config_apply_service
from open_bos_stream.core.container import config as runtime_config
from open_bos_stream.notifications.monitor import NotificationMonitor
from open_bos_stream.core.status_events import StatusEventTracker
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
    online_router as map_online_router,
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
from open_bos_stream.api.notifications import (
    router as notifications_router,
)
from open_bos_stream.api.guest import router as guest_router
from open_bos_stream.api.weather import router as weather_router
from open_bos_stream.api.organizations import router as organizations_router
from open_bos_stream.api.push import router as push_router
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
            if not available and recording_service.recording_active:
                message = media_storage_service.blocked_message()
                logger.warning(
                    "Laufende Aufnahmen werden wegen Speichermangel beendet."
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


def report_expired_guest_links(previously_active: set[str]) -> set[str]:
    """Meldet Gastlinks, die seit der letzten Prüfung abgelaufen sind."""

    links = guest_link_store.list()
    active = {link.id for link in links if link.active()}
    for link in links:
        if (
            link.id in previously_active
            and link.id not in active
            and link.revoked_at is None
        ):
            server_event_log.record(
                "info",
                f"🔗 Gastlink „{link.label}“ abgelaufen",
                organization_id=link.organization_id,
            )
    return active


async def notification_loop() -> None:
    """Erkennt Störungen und meldet sie per E-Mail und Web Push."""

    monitor = NotificationMonitor()
    tracker = StatusEventTracker()
    active_guest_links = await asyncio.to_thread(
        report_expired_guest_links,
        set(),
    )
    # Dienste beim Start kurz hochfahren lassen, damit MediaMTX und Quellen
    # nicht fälschlich als gestört gelten.
    await asyncio.sleep(15)
    while True:
        try:
            status = await asyncio.to_thread(dashboard_service.status)
            for notice in monitor.evaluate(status, time.monotonic()):
                notification_service.enqueue(notice)
                push_service.enqueue(notice)
            for level, message, organization_id in tracker.evaluate_detailed(status):
                server_event_log.record(
                    level,
                    message,
                    organization_id=organization_id,
                )
            active_guest_links = await asyncio.to_thread(
                report_expired_guest_links,
                active_guest_links,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Störungsüberwachung fehlgeschlagen.")
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialisiert die Anwendung."""

    server_event_log.record(
        "info",
        f"🚒 Open BOS Drohnen gestartet · Version {VERSION}",
    )

    # Datenbank vorbereiten, alte Benutzerdatei übernehmen und bestehende
    # Quellen der Start-Wehr zuordnen (nur beim ersten Start mit 0.21).
    organizations = auth_service.ready()
    assigned = config_apply_service.assign_unowned_sources(
        organizations.default_organization_id()
    )
    guest_link_store.assign_unowned(organizations.default_organization_id())
    if assigned:
        server_event_log.record(
            "info",
            "🏢 Quellen der Start-Organisation zugeordnet: " + ", ".join(assigned),
        )

    setup_code = auth_service.ensure_setup_code()
    if setup_code:
        logger.warning(
            "Ersteinrichtung ausstehend. Einrichtungscode: %s",
            setup_code,
        )

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
    notification_task = asyncio.create_task(notification_loop())

    try:
        yield
    finally:
        tasks = (recording_task, storage_task, notification_task)
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task

    server_event_log.record("info", "🚒 Open BOS Drohnen wird beendet")

    if recording_service.recording_active:
        try:
            recording_service.stop_all()
        except Exception:
            logger.exception(
                "Laufende Aufnahmen konnten nicht sauber beendet werden."
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
    title="Open BOS Drohnen",
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
# Online-Grundkarten vor den allgemeinen Offline-Kartenrouten.
app.include_router(map_online_router)
app.include_router(map_router)
app.include_router(mediamtx_auth_router)
app.include_router(notifications_router)
app.include_router(guest_router)
app.include_router(weather_router)
app.include_router(organizations_router)
app.include_router(push_router)
