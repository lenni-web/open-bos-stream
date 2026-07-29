from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.models import AppConfig, MediaMTXStatus
from open_bos_stream.stream.command import FFmpegCommandBuilder
from open_bos_stream.stream.service import StreamService
from open_bos_stream.stream.inputs.rtmp import repair_input_url
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


def test_repair_input_url_only_mirrors_local_mediamtx() -> None:
    assert repair_input_url(
        "rtmp://127.0.0.1:1935/live/drohne"
    ) == (
        "rtsp://127.0.0.1:8554/live/drohne",
        True,
    )
    assert repair_input_url(
        "rtmp://example.test/live/drohne"
    ) == (
        "rtmp://example.test/live/drohne",
        False,
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
    data["source_profile"] = "capture_card"
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


def test_rtmp_passthrough_profile_is_normalized() -> None:
    data = ConfigLoader().load().model_dump()
    data["source_profile"] = "rtmp_passthrough"
    data["input"]["type"] = "v4l2"
    data["encoder"]["codec"] = "h264_v4l2m2m"
    data["stream"]["name"] = "drohne"
    data["stream"]["passthrough"] = False

    config = AppConfig(**data)

    assert config.input.type == "rtmp"
    assert config.input.mode == "copy"
    assert config.encoder.codec == "copy"
    assert config.stream.passthrough is True
    assert config.stream.name == "live/drohne"
    assert config.input.url == (
        "rtmp://127.0.0.1:1935/live/drohne"
    )


def test_rtmp_repair_profile_uses_managed_copy_relay() -> None:
    data = ConfigLoader().load().model_dump()
    data["source_profile"] = "rtmp_repair"
    data["input"]["url"] = (
        "rtmp://127.0.0.1:1935/live/drohne"
    )
    data["stream"]["name"] = "live/drohne"

    config = AppConfig(**data)
    service = StreamService(
        config=config,
        mediamtx_service=FakeMediaMTXService(ready=False),
    )

    assert config.input.type == "rtmp"
    assert config.input.mode == "copy_repair"
    assert config.encoder.codec == "copy"
    assert config.stream.passthrough is False
    assert config.stream.name == "drohne"
    assert config.stream.rtsp_url == (
        "rtsp://127.0.0.1:8554/drohne"
    )
    assert service.managed is True


def test_rtmp_repair_command_normalizes_timestamps_without_transcoding() -> None:
    data = ConfigLoader().load().model_dump()
    data["source_profile"] = "rtmp_repair"
    data["input"]["url"] = (
        "rtmp://127.0.0.1:1935/live/drohne"
    )
    config = AppConfig(**data)

    command = FFmpegCommandBuilder(config).build()

    assert ["-c:v", "copy"] == command[
        command.index("-c:v"):command.index("-c:v") + 2
    ]
    assert "+genpts+discardcorrupt" in command
    assert (
        "rtsp://127.0.0.1:8554/live/drohne"
        in command
    )
    assert (
        "rtmp://127.0.0.1:1935/live/drohne"
        not in command
    )
    input_index = command.index(
        "rtsp://127.0.0.1:8554/live/drohne"
    )
    assert command[input_index - 3:input_index] == [
        "-rtsp_transport",
        "tcp",
        "-i",
    ]
    assert ["-use_wallclock_as_timestamps", "1"] == command[
        command.index("-use_wallclock_as_timestamps"):
        command.index("-use_wallclock_as_timestamps") + 2
    ]
    assert ["-map", "0:a:0?", "-c:a", "copy"] == command[
        command.index("0:a:0?") - 1:
        command.index("0:a:0?") + 3
    ]
    assert "-vf" not in command
    assert "-filter_complex" not in command


def test_custom_v4l2_cannot_enable_passthrough() -> None:
    data = ConfigLoader().load().model_dump()
    data["source_profile"] = "custom"
    data["input"]["type"] = "v4l2"
    data["encoder"]["codec"] = "copy"
    data["stream"]["passthrough"] = True

    config = AppConfig(**data)

    assert config.source_profile == "custom"
    assert config.input.mode == "transcode"
    assert config.encoder.codec == "h264_v4l2m2m"
    assert config.stream.passthrough is False


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


def test_copy_mode_never_builds_video_filters_or_overlay() -> None:
    config = ConfigLoader().load()
    config.encoder.codec = "copy"
    config.stream.overlay.source = "clock"

    command = FFmpegCommandBuilder(config).build()

    assert "-vf" not in command
    assert "-filter_complex" not in command
    assert config.stream.overlay.font not in " ".join(command)


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
    assert "streamid=" not in command[-1]


def test_srt_output_preserves_custom_connection_parameters() -> None:
    config = ConfigLoader().load()
    output = next(
        item
        for item in config.stream_outputs
        if item.type == "srt"
    ).model_copy(deep=True)
    output.url = (
        "srt://example.test:8890"
        "?streamid=publish:custom&latency=200"
    )

    command = StreamOutputCommandBuilder(config).build(output)
    target = command[-1]

    assert target.count("streamid=") == 1
    assert "streamid=publish%3Acustom" in target
    assert "latency=200" in target
    assert "mode=caller" in target
