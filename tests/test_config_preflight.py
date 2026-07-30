from pathlib import Path

import pytest

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.config_preflight import (
    ConfigPreflightError,
    ConfigPreflightValidator,
)
from open_bos_stream.core.models import AppConfig


def test_passthrough_preflight_does_not_require_ffmpeg() -> None:
    config = ConfigLoader().load()

    checks = ConfigPreflightValidator().validate(config)

    assert checks == ["Quelle 1: direkter RTMP-Pfad 'quelle-1'"]


def test_rtsp_preflight_rejects_invalid_url() -> None:
    data = ConfigLoader().load().model_dump()
    data["sources"] = [{
        "id": "kamera-1",
        "name": "Kamera 1",
        "type": "rtsp",
        "profile": "direct",
        "url": "http://127.0.0.1/kamera",
    }]
    config = AppConfig.model_validate(data)

    with pytest.raises(ConfigPreflightError, match="RTSP"):
        ConfigPreflightValidator().validate(config)


def test_capture_preflight_rejects_missing_device(
    tmp_path: Path,
) -> None:
    data = ConfigLoader().load().model_dump()
    data["sources"] = [{
        "id": "capture-1",
        "name": "Capture 1",
        "type": "v4l2",
        "profile": "transcode",
        "device": str(tmp_path / "missing-video"),
    }]
    config = AppConfig.model_validate(data)

    with pytest.raises(ConfigPreflightError, match="Capture-Gerät"):
        ConfigPreflightValidator().validate(config)
