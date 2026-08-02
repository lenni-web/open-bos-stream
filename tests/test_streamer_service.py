from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_streamer_service_uses_bounded_restart_backoff() -> None:
    unit = (
        ROOT / "scripts" / "open-bos-streamer.service"
    ).read_text(encoding="utf-8")
    installer = (
        ROOT / "scripts" / "install-service.sh"
    ).read_text(encoding="utf-8")

    assert "Restart=on-failure" in unit
    assert "RestartSteps=6" in unit
    assert "RestartMaxDelaySec=60s" in unit
    assert "StartLimitBurst=8" in unit
    assert (
        "python -m open_bos_stream.stream.runner"
        in unit
    )
    assert "SOURCE_STREAMER_SERVICE_FILE" in installer
    assert "RuntimeDirectory=open-bos-stream" in unit


def test_runner_monitors_real_ffmpeg_progress() -> None:
    runner = (
        ROOT / "src" / "open_bos_stream" / "stream" / "runner.py"
    ).read_text(encoding="utf-8")

    assert '"-progress"' in runner
    assert '"pipe:1"' in runner
    assert '"-loglevel"' in runner
    assert '"warning"' in runner
    assert '"-nostdin"' in runner
    assert "STALE_TIMEOUT_SECONDS" in runner
    assert "runtime.progress.stale" in runner
    assert "StreamRuntimeStatusStore" in runner
