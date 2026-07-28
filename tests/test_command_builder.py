from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.stream.command import FFmpegCommandBuilder


def test_build_command():

    config = ConfigLoader().load()

    builder = FFmpegCommandBuilder(config)

    command = builder.build()

    assert command[0] == "ffmpeg"

    assert "-f" in command

    assert config.input.url in command

    assert ["-c:v", "copy"] == command[
        command.index("-c:v"):command.index("-c:v") + 2
    ]

    assert config.stream.rtsp_url in command

    output_index = command.index(config.stream.rtsp_url)

    assert command[output_index - 4:output_index] == [
        "-rtsp_transport",
        "tcp",
        "-f",
        "rtsp",
    ]
