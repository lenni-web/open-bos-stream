"""
Application Container

Erzeugt alle Singleton-Services der Anwendung.
"""

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.config_apply import ConfigApplyService

from open_bos_stream.dashboard.service import DashboardService
from open_bos_stream.mediamtx.client import MediaMTXClient
from open_bos_stream.mediamtx.service import MediaMTXService
from open_bos_stream.recording.library import RecordingLibrary
from open_bos_stream.recording.service import RecordingService
from open_bos_stream.snapshot.library import SnapshotLibrary
from open_bos_stream.snapshot.service import SnapshotService
from open_bos_stream.stream.service import StreamService
from open_bos_stream.system.health import HealthService
from open_bos_stream.stream_output.manager import (
    StreamOutputManager,
)
from open_bos_stream.media.library import (
    MediaLibrary,
)
from open_bos_stream.stream_output.service import (
    StreamOutputService,
)
from open_bos_stream.system.info import (
    SystemInfoService,
)

# ---------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------

config = ConfigLoader().load()


# ---------------------------------------------------------
# Infrastruktur
# ---------------------------------------------------------

mediamtx_client = MediaMTXClient()

mediamtx_service = MediaMTXService(
    mediamtx_client
)


# ---------------------------------------------------------
# Services
# ---------------------------------------------------------

stream_service = StreamService(
    config=config,
    mediamtx_service=mediamtx_service,
)

stream_output_manager = StreamOutputManager(
    config
)

config_apply_service = ConfigApplyService(
    loader=ConfigLoader(),
    runtime_config=config,
    stream=stream_service,
    outputs=stream_output_manager,
)

stream_output_service = StreamOutputService(
    config=config,
    mediamtx=mediamtx_client,
    manager=stream_output_manager,
)

health_service = HealthService(
    config=config,
    stream_service=stream_service,
    mediamtx_service=mediamtx_service,
)

system_info_service = SystemInfoService()

recording_service = RecordingService(
    config=config,
    mediamtx=mediamtx_client,
)

snapshot_service = SnapshotService(
    config
)

dashboard_service = DashboardService(
    config=config,
    stream_service=stream_service,
    health_service=health_service,
    mediamtx_service=mediamtx_service,
    recording_service=recording_service,
    system_info_service=system_info_service,
    stream_output_service=stream_output_service,
)


# ---------------------------------------------------------
# Bibliotheken
# ---------------------------------------------------------

recording_library = RecordingLibrary()

snapshot_library = SnapshotLibrary()

media_library = MediaLibrary(
    recordings=recording_library,
    snapshots=snapshot_library,
)
