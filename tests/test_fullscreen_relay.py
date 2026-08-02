from __future__ import annotations

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.models import SourceConfig
from open_bos_stream.stream.fullscreen_relay import FullscreenRelayManager


class FakeProcess:
    pid = 1234

    def __init__(self) -> None:
        self.returncode = None
        self.signals: list[int] = []

    def poll(self):
        return self.returncode

    def send_signal(self, value: int) -> None:
        self.signals.append(value)
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self) -> None:
        self.returncode = -9


class FakeMediaMTX:
    def path(self, name: str):
        return {
            "name": name,
            "ready": True,
            "tracks2": [
                {
                    "codec": "H264",
                    "codecProps": {"width": 3840, "height": 2160},
                }
            ],
        }


def test_fullscreen_relay_is_shared_and_uses_main_url(monkeypatch) -> None:
    config = ConfigLoader().load()
    source = SourceConfig(
        id="camera-1",
        name="Kamera 1",
        type="rtsp",
        profile="direct",
        url="rtsp://camera/main",
        preview_url="rtsp://camera/sub",
    )
    config.sources = [source]
    starts: list[list[str]] = []
    process = FakeProcess()

    def fake_popen(command, **kwargs):
        starts.append(command)
        return process

    monkeypatch.setattr(
        "open_bos_stream.stream.fullscreen_relay.subprocess.Popen",
        fake_popen,
    )
    manager = FullscreenRelayManager(config, FakeMediaMTX())
    try:
        first = manager.acquire(source.id)
        second = manager.acquire(source.id)

        assert len(starts) == 1
        assert source.url in starts[0]
        assert source.preview_url not in starts[0]
        assert first["viewer_path"] == "camera-1-main"
        assert first["ready"] is True
        assert first["width"] == 3840
        assert first["height"] == 2160
        assert first["codec"] == "H264"
        assert first["lease_id"] != second["lease_id"]

        manager.release(source.id, first["lease_id"])
        assert second["lease_id"] in manager._relays[source.id].leases
    finally:
        manager.close()

    assert process.returncode == 0
