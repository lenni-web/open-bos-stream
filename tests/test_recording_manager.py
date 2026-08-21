from pathlib import Path
from types import SimpleNamespace
import time

import pytest

from open_bos_stream.recording.manager import RecordingManager


class FakeBuilder:
    def __init__(self) -> None:
        self.output: Path | None = None

    def build(self, filename: Path, input_url: str, **kwargs):
        self.output = filename
        return ["ffmpeg", "-i", input_url, str(filename)]


class FakeProcess:
    running = False
    pid = 42
    last_error = ""

    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode

    def start(self, command: list[str]) -> None:
        Path(command[-1]).write_bytes(b"mp4-data")
        self.running = True

    def stop(self) -> int:
        self.running = False
        return self.returncode


def manager_with_fakes(returncode: int = 0):
    manager = RecordingManager()
    builder = FakeBuilder()
    manager._builder = builder
    manager._process = FakeProcess(returncode)
    return manager, builder


def test_recording_is_published_only_after_validation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    manager, builder = manager_with_fakes()
    final = tmp_path / "recording_test.mp4"
    monkeypatch.setattr(
        "open_bos_stream.recording.manager.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="video\n",
            stderr="",
        ),
    )

    manager.start(final, "rtsp://127.0.0.1/source")

    assert not final.exists()
    assert builder.output is not None
    assert builder.output.name.endswith(".part")

    manager.stop()

    assert final.read_bytes() == b"mp4-data"
    assert not builder.output.exists()


def test_failed_recording_is_discarded(tmp_path: Path) -> None:
    manager, builder = manager_with_fakes(returncode=1)
    manager._process.last_error = "broken timestamps"
    final = tmp_path / "recording_test.mp4"

    manager.start(final, "rtsp://127.0.0.1/source")

    with pytest.raises(RuntimeError, match="broken timestamps"):
        manager.stop()

    assert not final.exists()
    assert builder.output is not None
    assert not builder.output.exists()


def test_nonzero_ffmpeg_exit_keeps_valid_finalized_recording(
    monkeypatch,
    tmp_path: Path,
) -> None:
    manager, builder = manager_with_fakes(returncode=255)
    manager._process.last_error = "Could not find ref with POC 47"
    final = tmp_path / "recording_test.mp4"
    monkeypatch.setattr(
        "open_bos_stream.recording.manager.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="video\n",
            stderr="",
        ),
    )

    manager.start(final, "rtsp://127.0.0.1/source")
    manager.stop()

    assert final.read_bytes() == b"mp4-data"
    assert builder.output is not None
    assert not builder.output.exists()


def test_unexpected_exit_automatically_publishes_valid_partial_recording(
    monkeypatch,
    tmp_path: Path,
) -> None:
    manager, builder = manager_with_fakes(returncode=1)
    final = tmp_path / "recording_interrupted.mp4"
    monkeypatch.setattr(
        "open_bos_stream.recording.manager.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="video\n",
            stderr="",
        ),
    )

    manager.start(final, "rtsp://127.0.0.1/source")
    manager._process.running = False

    deadline = time.monotonic() + 2
    while manager.last_outcome is None and time.monotonic() < deadline:
        time.sleep(0.02)

    assert final.read_bytes() == b"mp4-data"
    assert builder.output is not None
    assert not builder.output.exists()
    assert manager.last_outcome is not None
    assert manager.last_outcome.reason == "stream_interrupted"
    assert manager.last_outcome.filename == str(final)


def test_unexpected_exit_discards_invalid_partial_recording(
    monkeypatch,
    tmp_path: Path,
) -> None:
    manager, builder = manager_with_fakes(returncode=1)
    final = tmp_path / "recording_invalid.mp4"
    monkeypatch.setattr(
        "open_bos_stream.recording.manager.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="moov atom not found",
        ),
    )

    manager.start(final, "rtsp://127.0.0.1/source")
    manager._process.running = False

    deadline = time.monotonic() + 2
    while manager.last_outcome is None and time.monotonic() < deadline:
        time.sleep(0.02)

    assert not final.exists()
    assert builder.output is not None
    assert not builder.output.exists()
    assert manager.last_outcome is not None
    assert manager.last_outcome.reason == "failed"
    assert manager.last_outcome.filename is None
