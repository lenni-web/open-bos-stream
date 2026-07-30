from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.models import AppConfig
from open_bos_stream.mediamtx.service import MediaMTXService


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
