import json
import time
from pathlib import Path

from open_bos_stream.stream.progress import FFmpegProgress
from open_bos_stream.stream.runner import SourceProcess, _runtime_snapshot
from open_bos_stream.stream.runtime_status import StreamRuntimeStatusStore


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
        "last_progress_at": 999.0,
    }
