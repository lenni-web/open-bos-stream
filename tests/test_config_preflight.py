from pathlib import Path

import pytest

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.config_preflight import (
    ConfigPreflightError,
    ConfigPreflightValidator,
)
from open_bos_stream.core.models import AppConfig


def test_passthrough_preflight_does_not_require_ffmpeg() -> None:
    data = ConfigLoader().load().model_dump()
    data["source_profile"] = "rtmp_passthrough"
    data["input"]["url"] = "rtmp://127.0.0.1:1935/live/drohne"
    config = AppConfig.model_validate(data)

    checks = ConfigPreflightValidator().validate(config)

    assert len(checks) == 3
    assert any("RTMP" in check for check in checks)


def test_passthrough_preflight_rejects_invalid_url() -> None:
    data = ConfigLoader().load().model_dump()
    data["source_profile"] = "rtmp_passthrough"
    config = AppConfig.model_validate(data)
    config.input.url = "http://127.0.0.1/live/drohne"

    with pytest.raises(ConfigPreflightError, match="RTMP"):
        ConfigPreflightValidator().validate(config)


def test_capture_preflight_rejects_missing_device(
    tmp_path: Path,
) -> None:
    data = ConfigLoader().load().model_dump()
    data["source_profile"] = "capture_card"
    data["input"]["device"] = str(tmp_path / "missing-video")
    config = AppConfig.model_validate(data)

    with pytest.raises(ConfigPreflightError, match="Capture-Gerät"):
        ConfigPreflightValidator().validate(config)
