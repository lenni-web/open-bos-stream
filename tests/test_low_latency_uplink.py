"""Raspberry Pi vor Ort: Capture-Card latenzarm kodieren und per SRT senden."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.models import SourceConfig, StreamOutputConfig
from open_bos_stream.stream.command import FFmpegCommandBuilder
from open_bos_stream.stream_output.command import StreamOutputCommandBuilder

ROOT = Path(__file__).resolve().parents[1]


def capture_source(**overrides) -> SourceConfig:
    values = {
        "id": "hdmi",
        "name": "HDMI vor Ort",
        "type": "v4l2",
        "device": "/dev/video0",
        "format": "mjpeg",
        "width": 1280,
        "height": 720,
        "fps": 25,
        "profile": "transcode_low_latency",
        "codec": "h264_v4l2m2m",
        "bitrate": "2500k",
    }
    values.update(overrides)
    return SourceConfig(**values)


def option(command: list[str], name: str) -> str:
    return command[command.index(name) + 1]


def test_low_latency_capture_uses_hardware_encoder_without_b_frames() -> None:
    config = ConfigLoader().load()
    source = capture_source()

    command = FFmpegCommandBuilder(config).build(source_override=source)

    # Eingangspuffer aus, vor dem Eingang.
    assert command.index("nobuffer") < command.index("-i")
    assert option(command, "-c:v") == "h264_v4l2m2m"
    assert option(command, "-bf") == "0"
    # Ein Schlüsselbild pro Sekunde bei 25 fps.
    assert option(command, "-g") == "25"
    assert option(command, "-keyint_min") == "25"
    assert option(command, "-flush_packets") == "1"
    assert command[-1] == "rtsp://127.0.0.1:8554/hdmi-view"


def test_low_latency_software_fallback_uses_zerolatency() -> None:
    config = ConfigLoader().load()
    source = capture_source(codec="libx264")

    command = FFmpegCommandBuilder(config).build(source_override=source)

    assert option(command, "-c:v") == "libx264"
    assert option(command, "-preset") == "ultrafast"
    assert option(command, "-tune") == "zerolatency"


def test_regular_transcode_keeps_previous_behaviour() -> None:
    config = ConfigLoader().load()
    source = capture_source(profile="transcode")

    command = FFmpegCommandBuilder(config).build(source_override=source)

    assert "nobuffer" not in command
    assert "-bf" not in command


def test_srt_uplink_to_open_bos_server_keeps_token_and_adds_latency() -> None:
    config = ConfigLoader().load()
    output = StreamOutputConfig(
        type="srt",
        name="Zum Server",
        url=(
            "srt://ffw.example:8890"
            "?streamid=publish:pi-vor-ort:token=ABCdef123456"
            "&pkt_size=1316"
        ),
    )

    command = StreamOutputCommandBuilder(config).build(output)
    query = parse_qs(urlsplit(command[-1]).query)

    # FFmpeg dekodiert die streamid; nach dem Dekodieren muss sie exakt dem
    # Anmeldeformat von MediaMTX entsprechen.
    assert unquote(query["streamid"][0]) == "publish:pi-vor-ort:token=ABCdef123456"
    assert query["latency"] == ["400000"]
    assert query["mode"] == ["caller"]
    assert option(command, "-c:v") == "copy"
    assert command.index("nobuffer") < command.index("-i")
    assert option(command, "-flush_packets") == "1"
    assert option(command, "-f") == "mpegts"


def test_rtsp_controller_presets_relay_without_transcoding() -> None:
    script = (
        ROOT / "src" / "open_bos_stream" / "static" / "js"
        / "config_rtmp_inputs.js"
    ).read_text(encoding="utf-8")

    assert "RTSP_CONTROLLER_PRESETS" in script
    for preset in ('id: "dji-pilot2"', 'id: "parrot"', 'id: "skydio"', 'id: "autel"'):
        assert preset in script
    assert 'url: "rtsp://192.168.53.1/live"' in script
    assert 'profile.value = "copy_repair_low_latency"' in script
    assert 'data-role="rtsp-preset"' in script


def test_rtsp_source_relays_to_srt_output_unchanged() -> None:
    config = ConfigLoader().load().model_copy(deep=True)
    config.sources = [
        SourceConfig(
            id="parrot",
            name="Parrot",
            type="rtsp",
            profile="copy_repair_low_latency",
            transport="udp",
            url="rtsp://192.168.53.1/live",
        )
    ]
    output = StreamOutputConfig(
        type="srt",
        name="Zum Server",
        source_id="parrot",
        url="srt://ffw.example:8890?streamid=publish:pi:token=ABCdef123456",
    )

    relay = StreamOutputCommandBuilder(config).build(output)
    assert "rtsp://127.0.0.1:8554/parrot-view" in relay
    assert option(relay, "-c:v") == "copy"

    pull = FFmpegCommandBuilder(config).build_source(config.sources[0])
    assert option(pull, "-rtsp_transport") == "udp"
    assert option(pull, "-c:v") == "copy"


def test_pi_controller_network_keeps_mobile_default_route() -> None:
    script = (ROOT / "scripts" / "pi-controller-network.sh").read_text(
        encoding="utf-8"
    )

    assert "ipv4.never-default yes" in script
    assert "configure auto" in script
    assert "configure shared" in script
    assert "lokales Profil" in script
