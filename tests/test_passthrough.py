from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.models import AppConfig, MediaMTXStatus
from open_bos_stream.stream.command import FFmpegCommandBuilder
from open_bos_stream.stream.service import StreamService
from open_bos_stream.stream_output.command import (
    StreamOutputCommandBuilder,
)


class FakeMediaMTXService:
    def __init__(self, ready: bool) -> None:
        self.ready = ready
        self.requested_paths: list[str] = []

    def status(self, path: str) -> MediaMTXStatus:
        self.requested_paths.append(path)

        return MediaMTXStatus(
            online=True,
            publisher=self.ready,
            path=path,
            ready=self.ready,
        )


def test_passthrough_uses_mediamtx_path_without_pid() -> None:
    config = ConfigLoader().load()
    mediamtx = FakeMediaMTXService(ready=True)
    service = StreamService(
        config=config,
        mediamtx_service=mediamtx,
    )

    assert config.stream.passthrough is True
    assert service.managed is False
    assert service.running is True
    assert service.pid is None
    assert mediamtx.requested_paths == ["live/drohne"]


def test_passthrough_waits_for_external_publisher() -> None:
    config = ConfigLoader().load()
    service = StreamService(
        config=config,
        mediamtx_service=FakeMediaMTXService(ready=False),
    )

    try:
        service.start()
    except RuntimeError as exc:
        assert "Warte auf einen Publisher" in str(exc)
    else:
        raise AssertionError("start() must wait for the external publisher")


def test_capture_card_always_uses_managed_streamer() -> None:
    config = ConfigLoader().load()
    config.input.type = "v4l2"
    config.encoder.codec = "h264_v4l2m2m"
    config.stream.passthrough = True

    service = StreamService(
        config=config,
        mediamtx_service=FakeMediaMTXService(ready=False),
    )

    assert config.passthrough_active is False
    assert service.managed is True


def test_capture_card_config_is_normalized() -> None:
    data = ConfigLoader().load().model_dump()
    data["input"]["type"] = "v4l2"
    data["input"]["mode"] = "copy"
    data["encoder"]["codec"] = "copy"
    data["stream"]["passthrough"] = True
    data["stream"]["name"] = "live/drohne"
    data["stream"]["rtsp_url"] = (
        "rtsp://127.0.0.1:8554/live/drohne"
    )

    config = AppConfig(**data)

    assert config.input.mode == "transcode"
    assert config.encoder.codec == "h264_v4l2m2m"
    assert config.stream.passthrough is False
    assert config.stream.name == "drohne"
    assert config.stream.rtsp_url == (
        "rtsp://127.0.0.1:8554/drohne"
    )


def test_transcoding_rtsp_output_uses_tcp() -> None:
    config = ConfigLoader().load()
    config.stream.passthrough = False
    config.encoder.codec = "libx264"

    command = FFmpegCommandBuilder(config).build()
    output_index = command.index(config.stream.rtsp_url)

    assert command[output_index - 4:output_index] == [
        "-rtsp_transport",
        "tcp",
        "-f",
        "rtsp",
    ]


def test_srt_output_command_is_flat_and_uses_direct_stream() -> None:
    config = ConfigLoader().load()
    output = next(
        item
        for item in config.stream_outputs
        if item.type == "srt"
    )

    command = StreamOutputCommandBuilder(config).build(output)

    assert all(isinstance(item, str) for item in command)
    assert config.stream.rtsp_url in command
    assert ["-c:v", "copy"] == command[
        command.index("-c:v"):command.index("-c:v") + 2
    ]
    assert ["-c:a", "copy"] == command[
        command.index("-c:a"):command.index("-c:a") + 2
    ]
