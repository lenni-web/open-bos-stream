from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.stream.command import FFmpegCommandBuilder


def test_build_command():

    config = ConfigLoader().load()

    builder = FFmpegCommandBuilder(config)

    command = builder.build()

    assert command[0] == "ffmpeg"

    assert "-f" in command

    assert "v4l2" in command

    assert config.capture.device in command

    assert config.stream.rtsp_url in command
