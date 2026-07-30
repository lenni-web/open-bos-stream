from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.models import AppConfig
from open_bos_stream.core.models import SourceConfig
from open_bos_stream.mediamtx.service import MediaMTXService
from open_bos_stream.stream.command import FFmpegCommandBuilder
from open_bos_stream.stream.inputs import registry
from open_bos_stream.stream.runner import _redact


class FakeMediaMTXClient:
    def __init__(self) -> None:
        self.path_calls = 0

    def online(self) -> bool:
        return True

    def paths(self) -> list[dict]:
        self.path_calls += 1
        return [
            {
                "name": "live/quelle-1",
                "ready": True,
                "tracks": ["H264"],
                "tracks2": [
                    {
                        "codecProps": {
                            "width": 1280,
                            "height": 720,
                        }
                    }
                ],
                "readers": [],
                "source": {"type": "rtmpConn"},
            }
        ]


def test_up_to_eight_unique_rtmp_inputs_are_valid() -> None:
    data = ConfigLoader().load().model_dump()
    data["rtmp_inputs"] = [
        {
            "id": f"quelle-{index}",
            "name": f"Quelle {index}",
            "path": f"live/quelle-{index}",
        }
        for index in range(1, 9)
    ]

    config = AppConfig.model_validate(data)

    assert len(config.rtmp_inputs) == 8


def test_more_than_eight_rtmp_inputs_are_rejected() -> None:
    data = ConfigLoader().load().model_dump()
    data["rtmp_inputs"] = [
        {
            "id": f"quelle-{index}",
            "name": f"Quelle {index}",
            "path": f"live/quelle-{index}",
        }
        for index in range(1, 10)
    ]

    with pytest.raises(ValidationError):
        AppConfig.model_validate(data)


def test_more_than_eight_unified_sources_are_rejected() -> None:
    data = ConfigLoader().load().model_dump()
    data["sources"] = [
        {
            "id": f"quelle-{index}",
            "name": f"Quelle {index}",
            "type": "rtmp",
        }
        for index in range(1, 10)
    ]

    with pytest.raises(ValidationError):
        AppConfig.model_validate(data)


def test_duplicate_rtmp_paths_are_rejected() -> None:
    data = ConfigLoader().load().model_dump()
    data["rtmp_inputs"] = [
        {
            "id": "quelle-1",
            "name": "Quelle 1",
            "path": "live/doppelt",
        },
        {
            "id": "quelle-2",
            "name": "Quelle 2",
            "path": "live/doppelt",
        },
    ]

    with pytest.raises(ValidationError):
        AppConfig.model_validate(data)


def test_legacy_rtmp_config_becomes_first_input(
    tmp_path: Path,
) -> None:
    data = ConfigLoader().load().model_dump()
    data.pop("rtmp_inputs")
    data["input"]["type"] = "rtmp"
    data["input"]["mode"] = "copy_repair"
    data["input"]["url"] = (
        "rtmp://127.0.0.1:1935/live/drohne"
    )
    data["stream"]["name"] = "drohne"
    config_file = tmp_path / "stream.yaml"
    config_file.write_text(
        yaml.safe_dump(data),
        encoding="utf-8",
    )

    config = ConfigLoader(str(config_file)).load()

    assert config.rtmp_inputs[0].path == "live/drohne"
    assert config.rtmp_inputs[0].viewer_path == "drohne"


def test_legacy_main_and_rtmp_slots_become_equal_sources(
    tmp_path: Path,
) -> None:
    data = ConfigLoader().load().model_dump()
    data["sources"] = []
    data["source_profile"] = "rtmp_repair"
    data["input"]["type"] = "rtmp"
    data["input"]["mode"] = "copy_repair"
    data["input"]["url"] = (
        "rtmp://127.0.0.1:1935/live/drohne"
    )
    data["rtmp_inputs"] = [
        {
            "id": "drohne",
            "name": "Drohne",
            "path": "live/drohne",
            "viewer_path": "drohne-alt",
            "enabled": True,
        },
        {
            "id": "kamera-2",
            "name": "Kamera 2",
            "path": "live/kamera-2",
            "enabled": True,
        },
    ]
    config_file = tmp_path / "stream.yaml"
    config_file.write_text(
        yaml.safe_dump(data),
        encoding="utf-8",
    )

    config = ConfigLoader(str(config_file)).load()

    assert [source.id for source in config.sources] == [
        "drohne",
        "kamera-2",
    ]
    assert config.sources[0].profile == "copy_repair"
    assert config.sources[1].profile == "direct"
    assert config.sources[0].url == (
        "rtmp://127.0.0.1:1935/drohne"
    )


def test_multiple_mediamtx_paths_use_one_list_request() -> None:
    client = FakeMediaMTXClient()
    service = MediaMTXService(client)  # type: ignore[arg-type]

    statuses = service.statuses([
        "live/quelle-1",
        "live/quelle-2",
    ])

    assert client.path_calls == 1
    assert statuses["live/quelle-1"].ready is True
    assert statuses["live/quelle-2"].ready is False


def test_registered_source_types_are_available_for_sources() -> None:
    assert {
        item.type
        for item in registry.all()
    } == {
        "v4l2",
        "rtmp",
        "rtsp",
        "srt",
        "udp",
        "http",
        "hls",
    }


def test_rtmp_path_is_always_derived_from_source_id() -> None:
    source = SourceConfig(
        id="kamera_1",
        name="Kamera 1",
        type="rtmp",
        profile="copy_repair",
        url="rtmp://example.invalid/anderer-pfad",
    )

    assert source.publish_path == "kamera_1"
    assert source.url == "rtmp://127.0.0.1:1935/kamera_1"
    assert source.viewer_path == "kamera_1-view"


@pytest.mark.parametrize(
    "source_id",
    ["", "Quelle 1", "quelle/1", "äöü", "-quelle"],
)
def test_source_id_rejects_spaces_and_special_characters(
    source_id: str,
) -> None:
    with pytest.raises(ValidationError):
        SourceConfig(
            id=source_id,
            name="Quelle",
            type="rtmp",
        )


def test_rtsp_direct_copy_uses_independent_viewer_path() -> None:
    config = ConfigLoader().load()
    source = SourceConfig(
        id="reolink-1",
        name="Reolink 1",
        type="rtsp",
        profile="direct",
        url="rtsp://admin:secret@192.168.1.50/Preview_01_main",
        audio_mode="aac",
    )

    command = FFmpegCommandBuilder(config).build_source(source)

    assert source.url in command
    assert ["-c:v", "copy"] == command[
        command.index("-c:v"):command.index("-c:v") + 2
    ]
    assert ["-c:a", "aac"] == command[
        command.index("-c:a"):command.index("-c:a") + 2
    ]
    assert (
        "rtsp://127.0.0.1:8554/reolink-1-view"
        in command
    )


def test_each_source_can_select_timestamp_repair() -> None:
    config = ConfigLoader().load()
    source = SourceConfig(
        id="drohne-2",
        name="Drohne 2",
        type="rtmp",
        profile="copy_repair",
    )

    command = FFmpegCommandBuilder(config).build_source(source)

    assert "+genpts+discardcorrupt+nobuffer" in command
    assert "rtsp://127.0.0.1:8554/drohne-2" in command
    assert "rtsp://127.0.0.1:8554/drohne-2-view" in command


def test_network_credentials_are_redacted_from_runner_logs() -> None:
    assert _redact(
        "rtsp://admin:secret@192.168.1.50:554/stream"
    ) == "rtsp://admin:***@192.168.1.50:554/stream"
    assert _redact(
        "srt://example.test:8890?passphrase=secret"
    ) == "srt://example.test:8890?***"
