from pathlib import Path

import pytest

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.config_apply import (
    ConfigApplyError,
    ConfigApplyService,
)
from open_bos_stream.core.models import AppConfig


class FakeLoader:
    def __init__(self) -> None:
        self.saved: list[AppConfig] = []

    def save(self, config: AppConfig) -> None:
        self.saved.append(config.model_copy(deep=True))


class FakeReloadable:
    def __init__(self) -> None:
        self.config: AppConfig | None = None

    def reload(self, config: AppConfig) -> None:
        self.config = config


class FakePreflight:
    def __init__(self) -> None:
        self.validated: list[AppConfig] = []

    def validate(self, config: AppConfig) -> list[str]:
        self.validated.append(config)
        return ["Testprüfung"]


class FakeStream(FakeReloadable):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.ready = True
        self.restarts = 0
        self.stops = 0

    @property
    def managed(self) -> bool:
        assert self.config is not None
        return not self.config.passthrough_active

    def start(self) -> bool:
        return True

    def stop(self) -> bool:
        self.stops += 1
        return True

    def restart(self) -> bool:
        self.restarts += 1
        return True

    def wait_until_ready(self, timeout: float = 8.0) -> bool:
        return self.ready


def capture_config(
    base: AppConfig,
    device: Path,
) -> AppConfig:
    data = base.model_dump()
    data["source_profile"] = "capture_card"
    data["input"]["device"] = str(device)
    return AppConfig(**data)


def test_capture_profile_is_activated_atomically(
    tmp_path: Path,
) -> None:
    device = tmp_path / "video0"
    device.touch()

    data = ConfigLoader().load().model_dump()
    data["source_profile"] = "rtmp_passthrough"
    runtime = AppConfig.model_validate(data)
    candidate = capture_config(runtime, device)
    loader = FakeLoader()
    stream = FakeStream(runtime)
    outputs = FakeReloadable()
    service = ConfigApplyService(
        loader,
        runtime,
        stream,
        outputs,
        FakePreflight(),
    )

    message = service.apply(candidate)

    assert runtime.source_profile == "capture_card"
    assert runtime.input.type == "v4l2"
    assert stream.restarts == 1
    assert stream.stops == 0
    assert len(loader.saved) == 1
    assert "aktiviert" in message


def test_failed_capture_activation_rolls_back(
    tmp_path: Path,
) -> None:
    device = tmp_path / "video0"
    device.touch()

    runtime = ConfigLoader().load()
    runtime.source_profile = "rtmp_passthrough"
    runtime = AppConfig.model_validate(runtime.model_dump())
    candidate = capture_config(runtime, device)
    loader = FakeLoader()
    stream = FakeStream(runtime)
    stream.ready = False
    outputs = FakeReloadable()
    service = ConfigApplyService(
        loader,
        runtime,
        stream,
        outputs,
        FakePreflight(),
    )

    with pytest.raises(ConfigApplyError):
        service.apply(candidate)

    assert runtime.source_profile == "rtmp_passthrough"
    assert runtime.passthrough_active is True
    assert stream.stops == 1
    assert len(loader.saved) == 2
    assert loader.saved[-1].source_profile == (
        "rtmp_passthrough"
    )
