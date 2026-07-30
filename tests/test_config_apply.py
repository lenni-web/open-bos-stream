from pathlib import Path

import pytest

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.config_apply import (
    ConfigApplyError,
    ConfigApplyService,
)
from open_bos_stream.core.models import (
    AppConfig,
    SourceConfig,
)


class FakeLoader:
    def __init__(self) -> None:
        self.saved: list[AppConfig] = []
        self.last_known_good: AppConfig | None = None

    def save(self, config: AppConfig) -> None:
        self.saved.append(config.model_copy(deep=True))

    def save_last_known_good(self, config: AppConfig) -> None:
        self.last_known_good = config.model_copy(deep=True)

    def load_last_known_good(self) -> AppConfig:
        if self.last_known_good is None:
            raise FileNotFoundError
        return self.last_known_good.model_copy(deep=True)


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
        return any(
            source.enabled and source.requires_process
            for source in self.config.sources
        )

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
    data["sources"] = [{
        "id": "capture-1",
        "name": "Capture 1",
        "type": "v4l2",
        "profile": "transcode",
        "device": str(device),
        "enabled": True,
    }]
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

    assert runtime.sources[0].type == "v4l2"
    assert stream.restarts == 1
    assert stream.stops == 0
    assert len(loader.saved) == 1
    assert loader.last_known_good is not None
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

    assert runtime.sources[0].type == "rtmp"
    assert runtime.sources[0].profile == "direct"
    assert stream.stops == 1
    assert len(loader.saved) == 2
    assert loader.saved[-1].source_profile == (
        "rtmp_passthrough"
    )


def test_configuration_test_does_not_persist_or_restart(
    tmp_path: Path,
) -> None:
    device = tmp_path / "video0"
    device.touch()
    runtime = ConfigLoader().load()
    candidate = capture_config(runtime, device)
    loader = FakeLoader()
    stream = FakeStream(runtime)
    preflight = FakePreflight()
    service = ConfigApplyService(
        loader,
        runtime,
        stream,
        FakeReloadable(),
        preflight,
    )

    checks = service.test(candidate)

    assert checks == ["Testprüfung"]
    assert loader.saved == []
    assert stream.restarts == 0
    assert preflight.validated == [candidate]


def test_direct_rtmp_source_applies_without_stream_restart() -> None:
    runtime = ConfigLoader().load()
    candidate = runtime.model_copy(deep=True)
    candidate.sources.append(
        SourceConfig(
            id="quelle-2",
            name="Quelle 2",
            type="rtmp",
            profile="direct",
            enabled=True,
        )
    )
    candidate = AppConfig.model_validate(
        candidate.model_dump()
    )
    loader = FakeLoader()
    stream = FakeStream(runtime)
    service = ConfigApplyService(
        loader,
        runtime,
        stream,
        FakeReloadable(),
        FakePreflight(),
    )

    message = service.apply(candidate)

    assert stream.restarts == 0
    assert len(runtime.sources) == 2
    assert loader.last_known_good is not None
    assert "direkte Quellen" in message
