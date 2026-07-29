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
