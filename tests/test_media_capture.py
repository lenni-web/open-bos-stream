from pathlib import Path

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.recording.service import RecordingService
from open_bos_stream.snapshot.service import SnapshotService


class FakeMediaMTX:
    def path(self, name: str):
        return {
            "name": name,
            "ready": True,
            "codec": "H264",
            "tracks": ["H264", "MPEG-4 Audio"],
        }


class FakeRunner:
    def __init__(self) -> None:
        self.command: list[str] | None = None

    def run(self, command, **_kwargs):
        self.command = list(command)
        Path(command[-1]).write_bytes(
            b"\xff\xd8" + (b"snapshot" * 256) + b"\xff\xd9"
        )


class FakeRecordingManager:
    running = False
    pid = 1234

    def __init__(self) -> None:
        self.input_url: str | None = None
        self.transcode_video: bool | None = None
        self.transcode_audio: bool | None = None
        self.hevc: bool | None = None

    def start(
        self,
        _filename: Path,
        input_url: str,
        *,
        transcode_video: bool = False,
        transcode_audio: bool = False,
        hevc: bool = False,
    ) -> bool:
        self.input_url = input_url
        self.transcode_video = transcode_video
        self.transcode_audio = transcode_audio
        self.hevc = hevc
        self.running = True
        return True

    def stop(self) -> bool:
        self.running = False
        return True


class FakeRecorder:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def next_filename(self, source_id: str) -> Path:
        return self.directory / f"recording_{source_id}_test.mp4"


def selected_second_source():
    config = ConfigLoader().load()
    first = config.sources[0]
    second = first.model_copy(
        update={"id": "drohne-2", "name": "Drohne 2"}
    )
    config.sources = [first, second]
    config.media_capture.source_id = second.id
    return config, second


def test_snapshot_uses_selected_source(tmp_path: Path) -> None:
    config, source = selected_second_source()
    runner = FakeRunner()
    service = SnapshotService(
        config,
        FakeMediaMTX(),
        directory=str(tmp_path),
        runner=runner,
    )

    filename = service.create()

    assert source.id in filename.name
    assert runner.command is not None
    assert (
        f"rtsp://127.0.0.1:8554/{source.viewer_path}"
        in runner.command
    )
    assert ["-skip_frame", "nokey"] == runner.command[
        runner.command.index("-skip_frame"):
        runner.command.index("-skip_frame") + 2
    ]
    assert filename.exists()
    assert not filename.with_name(f".{filename.name}.part").exists()


def test_recording_uses_and_remembers_selected_source(
    tmp_path: Path,
) -> None:
    config, source = selected_second_source()
    service = RecordingService(config, FakeMediaMTX())
    manager = FakeRecordingManager()
    service._manager_factory = lambda: manager
    service._recorder = FakeRecorder(tmp_path)

    service.start()

    assert manager.input_url == (
        f"rtsp://127.0.0.1:8554/{source.viewer_path}"
    )
    assert service.status.source_id == source.id
    assert service.status.source_name == source.name
    assert source.id in (service.status.filename or "")
    assert manager.transcode_video is False
    assert manager.transcode_audio is False


def test_media_source_falls_back_to_first_enabled_source(
    tmp_path: Path,
) -> None:
    config, first = selected_second_source()
    config.media_capture.source_id = "nicht-mehr-vorhanden"
    first = config.sources[0]
    runner = FakeRunner()
    service = SnapshotService(
        config,
        FakeMediaMTX(),
        directory=str(tmp_path),
        runner=runner,
    )

    service.create()

    assert runner.command is not None
    assert (
        f"rtsp://127.0.0.1:8554/{first.viewer_path}"
        in runner.command
    )


def test_h265_recording_keeps_original_video(tmp_path: Path) -> None:
    config, source = selected_second_source()

    class H265MediaMTX:
        def path(self, name: str):
            return {
                "name": name,
                "ready": True,
                "codec": "H265",
                "tracks": ["H265", "G711"],
            }

    service = RecordingService(config, H265MediaMTX())
    manager = FakeRecordingManager()
    service._manager_factory = lambda: manager
    service._recorder = FakeRecorder(tmp_path)

    service.start()

    # H.265 wird unverändert übernommen; nur fremdes Audio wird zu AAC.
    assert manager.transcode_video is False
    assert manager.hevc is True
    assert manager.transcode_audio is True


def test_automatic_recording_follows_source_signal(
    tmp_path: Path,
) -> None:
    config, source = selected_second_source()
    config.media_capture.automatic_source_ids = [source.id]

    class SwitchableMediaMTX:
        ready = True

        def path(self, name: str):
            return {
                "name": name,
                "ready": self.ready,
                "codec": "H264",
                "tracks": ["H264", "MPEG-4 Audio"],
            }

    mediamtx = SwitchableMediaMTX()
    service = RecordingService(config, mediamtx)
    manager = FakeRecordingManager()
    service._manager_factory = lambda: manager
    service._recorder = FakeRecorder(tmp_path)

    service.reconcile_automatic()

    assert manager.running is True
    assert service.status.source_id == source.id
    assert service.status.mode == "automatic"

    mediamtx.ready = False
    service.reconcile_automatic()
    assert manager.running is True

    service.reconcile_automatic()
    assert manager.running is False
    assert service.status.automatic_waiting is True


def test_manual_recording_commands_are_blocked_in_automatic_mode(
    tmp_path: Path,
) -> None:
    config, _source = selected_second_source()
    config.media_capture.automatic_source_ids = [_source.id]
    service = RecordingService(config, FakeMediaMTX())
    service._manager_factory = FakeRecordingManager
    service._recorder = FakeRecorder(tmp_path)

    try:
        service.start()
    except RuntimeError as exc:
        assert "automatisch" in str(exc)
    else:
        raise AssertionError("Manueller Start wurde nicht gesperrt")

    service.start(automatic=True)

    try:
        service.stop()
    except RuntimeError as exc:
        assert "automatisch" in str(exc)
    else:
        raise AssertionError("Manueller Stopp wurde nicht gesperrt")

    service.stop(automatic=True)
    assert service.status.recording is False


class FullStorage:
    def ensure_capacity(self) -> None:
        from open_bos_stream.media.storage import StorageFullError

        raise StorageFullError("Zu wenig freier Speicher.")


def test_full_storage_blocks_recordings_and_snapshots(
    tmp_path: Path,
) -> None:
    config, _source = selected_second_source()
    recording = RecordingService(config, FakeMediaMTX(), FullStorage())
    manager = FakeRecordingManager()
    recording._manager_factory = lambda: manager
    recording._recorder = FakeRecorder(tmp_path)
    runner = FakeRunner()
    snapshot = SnapshotService(
        config,
        FakeMediaMTX(),
        directory=str(tmp_path),
        runner=runner,
        storage=FullStorage(),
    )

    try:
        recording.start()
    except RuntimeError as exc:
        assert "Speicher" in str(exc)
    else:
        raise AssertionError("Aufnahme hätte gesperrt sein müssen.")
    try:
        snapshot.create()
    except RuntimeError as exc:
        assert "Speicher" in str(exc)
    else:
        raise AssertionError("Snapshot hätte gesperrt sein müssen.")

    assert manager.running is False
    assert runner.command is None


def test_storage_stop_finishes_running_recording(tmp_path: Path) -> None:
    config, _source = selected_second_source()
    service = RecordingService(config, FakeMediaMTX())
    stops = []

    class Manager(FakeRecordingManager):
        def stop(self, **kwargs) -> bool:
            stops.append(kwargs)
            self.running = False
            return True

    service._manager_factory = Manager
    service._recorder = FakeRecorder(tmp_path)
    service.start()

    service.stop_for_storage("Speicher voll.")

    assert stops == [{"reason": "storage_low", "message": "Speicher voll."}]
    assert service.status.recording is False


class FakeRelays:
    """Vollbild-Relay, dessen Hauptstream nach einer Abfrage bereit ist."""

    def __init__(self, ready_after: int = 1) -> None:
        self.ready_after = ready_after
        self.polls = 0
        self.acquired: list[str] = []
        self.released: list[tuple[str, str]] = []

    def acquire(self, source_id: str) -> dict:
        self.acquired.append(source_id)
        return {"lease_id": "lease-1", "ready": self.ready_after == 0}

    def status(self, source_id: str, lease_id: str) -> dict:
        self.polls += 1
        return {
            "lease_id": lease_id,
            "ready": self.polls >= self.ready_after,
        }

    def release(self, source_id: str, lease_id: str) -> None:
        self.released.append((source_id, lease_id))


def preview_source_config():
    config, source = selected_second_source()
    preview = source.model_copy(
        update={"profile": "preview_transcode"}
    )
    config.sources = [config.sources[0], preview]
    return config, preview


def test_recording_uses_original_stream_of_preview_source(
    tmp_path: Path,
) -> None:
    config, source = preview_source_config()
    relays = FakeRelays()
    service = RecordingService(config, FakeMediaMTX(), relays=relays)
    service._capture._sleep = lambda _seconds: None
    manager = FakeRecordingManager()
    service._manager_factory = lambda: manager
    service._recorder = FakeRecorder(tmp_path)

    service.start()

    assert source.viewer_path != source.fullscreen_viewer_path
    assert manager.input_url == (
        f"rtsp://127.0.0.1:8554/{source.fullscreen_viewer_path}"
    )
    assert service.status.full_quality is True
    assert relays.released == []

    service.stop()

    assert relays.released == [(source.id, "lease-1")]
    assert service.status.full_quality is None


def test_snapshot_uses_original_stream_and_releases_it(
    tmp_path: Path,
) -> None:
    config, source = preview_source_config()
    relays = FakeRelays(ready_after=0)
    runner = FakeRunner()
    service = SnapshotService(
        config,
        FakeMediaMTX(),
        directory=str(tmp_path),
        runner=runner,
        relays=relays,
    )

    service.create()

    assert (
        f"rtsp://127.0.0.1:8554/{source.fullscreen_viewer_path}"
        in runner.command
    )
    assert relays.released == [(source.id, "lease-1")]


def test_unavailable_original_stream_falls_back_to_preview(
    tmp_path: Path,
) -> None:
    config, source = preview_source_config()
    relays = FakeRelays(ready_after=10_000)
    service = RecordingService(config, FakeMediaMTX(), relays=relays)
    service._capture._timeout = 0
    manager = FakeRecordingManager()
    service._manager_factory = lambda: manager
    service._recorder = FakeRecorder(tmp_path)

    service.start()

    assert manager.input_url == (
        f"rtsp://127.0.0.1:8554/{source.viewer_path}"
    )
    assert service.status.full_quality is False
    assert relays.released == [(source.id, "lease-1")]


def test_unexpectedly_ended_recording_releases_original_stream(
    tmp_path: Path,
) -> None:
    config, source = preview_source_config()
    relays = FakeRelays(ready_after=0)
    service = RecordingService(config, FakeMediaMTX(), relays=relays)
    manager = FakeRecordingManager()
    service._manager_factory = lambda: manager
    service._recorder = FakeRecorder(tmp_path)
    service.start()

    manager.running = False
    service.maintain()

    assert relays.released == [(source.id, "lease-1")]



# ----------------------------------------------------------------------
# Mehrere automatische Aufnahmen
# ----------------------------------------------------------------------


class SwitchableReadyMediaMTX:
    def __init__(self) -> None:
        self.ready: dict[str, bool] = {}

    def path(self, name: str):
        return {
            "name": name,
            "ready": self.ready.get(name, True),
            "codec": "H264",
            "tracks": ["H264", "MPEG-4 Audio"],
        }


def sources_config(count: int):
    config = ConfigLoader().load()
    first = config.sources[0]
    config.sources = [
        first.model_copy(update={"id": f"drohne-{index}", "name": f"Drohne {index}"})
        for index in range(1, count + 1)
    ]
    config.media_capture.source_id = "drohne-1"
    return config


def multi_service(tmp_path: Path, config, mediamtx):
    managers: list[FakeRecordingManager] = []

    def factory():
        manager = FakeRecordingManager()
        managers.append(manager)
        return manager

    service = RecordingService(config, mediamtx, manager_factory=factory)
    service._recorder = FakeRecorder(tmp_path)
    return service, managers


def test_two_sources_record_automatically_in_parallel(tmp_path: Path) -> None:
    config = sources_config(3)
    config.media_capture.automatic_source_ids = ["drohne-1", "drohne-2"]
    mediamtx = SwitchableReadyMediaMTX()
    service, _ = multi_service(tmp_path, config, mediamtx)

    service.reconcile_automatic()

    running = {item.source_id: item.recording for item in service.statuses()}
    assert running == {"drohne-1": True, "drohne-2": True, "drohne-3": False}
    assert service.recording_active

    # Drohne 2 verliert das Signal: nur ihre Aufnahme endet.
    viewer = next(s for s in config.sources if s.id == "drohne-2").viewer_path
    mediamtx.ready[viewer] = False
    service.reconcile_automatic()
    service.reconcile_automatic()
    running = {item.source_id: item.recording for item in service.statuses()}
    assert running["drohne-1"] is True
    assert running["drohne-2"] is False


def test_manual_recording_of_other_source_runs_alongside(tmp_path: Path) -> None:
    config = sources_config(2)
    config.media_capture.source_id = "drohne-2"
    config.media_capture.automatic_source_ids = ["drohne-1"]
    service, _ = multi_service(tmp_path, config, SwitchableReadyMediaMTX())

    service.reconcile_automatic()
    service.start()  # manuelle Aufnahme der Medienquelle Drohne 2

    assert service.status.source_id == "drohne-2"
    assert service.status.recording is True
    assert service.status.mode == "manual"
    assert [s.recording for s in service.statuses()] == [True, True]


def test_more_than_four_parallel_recordings(tmp_path: Path) -> None:
    config = sources_config(6)
    config.media_capture.source_id = "drohne-6"
    config.media_capture.automatic_source_ids = [
        "drohne-1", "drohne-2", "drohne-3", "drohne-4", "drohne-5",
    ]
    service, _ = multi_service(tmp_path, config, SwitchableReadyMediaMTX())
    service.reconcile_automatic()
    # Keine feste Obergrenze mehr: auch die sechste Aufnahme startet.
    service.start()

    assert sum(item.recording for item in service.statuses()) == 6


def test_removing_source_from_automatic_stops_its_recording(tmp_path: Path) -> None:
    config = sources_config(2)
    config.media_capture.automatic_source_ids = ["drohne-1", "drohne-2"]
    service, _ = multi_service(tmp_path, config, SwitchableReadyMediaMTX())
    service.reconcile_automatic()

    config.media_capture.automatic_source_ids = ["drohne-1"]
    service.reconcile_automatic()

    running = {item.source_id: item.recording for item in service.statuses()}
    assert running == {"drohne-1": True, "drohne-2": False}


def test_storage_stop_and_shutdown_finish_all_recordings(tmp_path: Path) -> None:
    config = sources_config(2)
    config.media_capture.automatic_source_ids = ["drohne-1", "drohne-2"]
    service, managers = multi_service(tmp_path, config, SwitchableReadyMediaMTX())
    service.reconcile_automatic()
    assert sum(manager.running for manager in managers) == 2

    stops = []
    for manager in managers:
        manager.stop = (
            lambda manager=manager, **kwargs: (
                stops.append(kwargs), setattr(manager, "running", False)
            )
        )
    service.stop_for_storage("Speicher voll.")
    assert len(stops) == 2
    assert all(item["reason"] == "storage_low" for item in stops)
    assert not service.recording_active


def test_legacy_automatic_mode_is_migrated() -> None:
    from open_bos_stream.core.models import MediaCaptureConfig

    legacy = MediaCaptureConfig(source_id="drohne-1", recording_mode="automatic")
    assert legacy.automatic_source_ids == ["drohne-1"]

    config = sources_config(2).model_dump()
    config["media_capture"] = {"recording_mode": "automatic"}
    from open_bos_stream.core.models import AppConfig

    migrated = AppConfig.model_validate(config).media_capture
    assert migrated.automatic_source_ids == ["drohne-1"]

    many = MediaCaptureConfig(automatic_source_ids=["a", "b", "c", "d", "e", "f"])
    assert len(many.automatic_source_ids) == 6
