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

    def start(
        self,
        _filename: Path,
        input_url: str,
        *,
        transcode_video: bool = False,
        transcode_audio: bool = False,
    ) -> bool:
        self.input_url = input_url
        self.transcode_video = transcode_video
        self.transcode_audio = transcode_audio
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
    service._manager = manager
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


def test_h265_recording_is_transcoded_for_browser(tmp_path: Path) -> None:
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
    service._manager = manager
    service._recorder = FakeRecorder(tmp_path)

    service.start()

    assert manager.transcode_video is True
    assert manager.transcode_audio is True


def test_automatic_recording_follows_source_signal(
    tmp_path: Path,
) -> None:
    config, source = selected_second_source()
    config.media_capture.recording_mode = "automatic"

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
    service._manager = manager
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
    config.media_capture.recording_mode = "automatic"
    service = RecordingService(config, FakeMediaMTX())
    service._manager = FakeRecordingManager()
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
