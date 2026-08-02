import json
import time
from pathlib import Path

from open_bos_stream.stream.progress import FFmpegProgress
from open_bos_stream.stream.runner import (
    RestartState,
    SourceProcess,
    _runtime_snapshot,
    _ready_paths,
    _waiting_for_publisher,
    _staggered_delay,
)
from open_bos_stream.stream.runtime_status import StreamRuntimeStatusStore
from open_bos_stream.core.models import SourceConfig


def test_runtime_status_roundtrip_is_atomic(tmp_path: Path) -> None:
    path = tmp_path / "runtime" / "progress.json"
    store = StreamRuntimeStatusStore(path)

    store.write({"quelle-1": {"state": "running", "fps": 29.97}})

    assert store.read()["quelle-1"] == {
        "state": "running",
        "fps": 29.97,
    }
    assert not path.with_suffix(".tmp").exists()


def test_stale_runtime_status_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    path.write_text(json.dumps({
        "updated_at": time.time() - 30,
        "sources": {"quelle-1": {"state": "running"}},
    }), encoding="utf-8")

    assert StreamRuntimeStatusStore(path).read(max_age=5) == {}


def test_runtime_snapshot_contains_compact_per_source_metrics(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "open_bos_stream.stream.runner.time.time",
        lambda: 1_000.0,
    )
    progress = FFmpegProgress(
        frame=120,
        fps=29.97,
        speed=1.01,
        dropped_frames=2,
        duplicated_frames=1,
        last_advance=49.0,
    )
    runtime = SourceProcess(
        process=None,  # type: ignore[arg-type]
        started_at=20.0,
        progress=progress,
        cpu_percent=17.5,
        memory_bytes=42_000_000,
    )

    snapshot = _runtime_snapshot(
        ["quelle-1"],
        {"quelle-1": runtime},
        {"quelle-1": 0.0},
        {"quelle-1": RestartState()},
        now=50.0,
    )["quelle-1"]

    assert snapshot == {
        "state": "running",
        "frame": 120,
        "fps": 29.97,
        "speed": 1.01,
        "drop_frames": 2,
        "dup_frames": 1,
        "cpu_percent": 17.5,
        "memory_bytes": 42_000_000,
        "last_drop_at": None,
        "last_dup_at": None,
        "restart_count": 0,
        "last_restart_reason": None,
        "last_restart_at": None,
        "last_progress_at": 999.0,
    }


def test_reconnect_delay_is_bounded_and_staggered_per_source() -> None:
    first = _staggered_delay("quelle-1", 30.0)
    second = _staggered_delay("quelle-2", 30.0)

    assert 30.0 <= first <= 36.0
    assert 30.0 <= second <= 36.0
    assert first != second


def test_only_ready_mediamtx_paths_start_rtmp_relays() -> None:
    assert _ready_paths([
        {"name": "quelle-1", "ready": True},
        {"name": "quelle-2", "ready": False},
        {"ready": True},
    ]) == {"quelle-1"}

    rtmp = SourceConfig(
        id="quelle-1",
        name="Quelle 1",
        type="rtmp",
        profile="copy_repair",
    )
    rtsp = SourceConfig(
        id="kamera-1",
        name="Kamera 1",
        type="rtsp",
        url="rtsp://camera/main",
    )
    assert _waiting_for_publisher(rtmp, set()) is True
    assert _waiting_for_publisher(rtmp, {"quelle-1"}) is False
    assert _waiting_for_publisher(rtsp, set()) is False


def test_runtime_snapshot_distinguishes_waiting_for_publisher() -> None:
    snapshot = _runtime_snapshot(
        ["quelle-1"],
        {},
        {"quelle-1": 50.0},
        {"quelle-1": RestartState()},
        {"quelle-1"},
        now=50.0,
    )

    assert snapshot["quelle-1"]["state"] == "waiting_source"
    assert snapshot["quelle-1"]["restart_count"] == 0
