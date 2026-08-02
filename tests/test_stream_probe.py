import json

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.process import ProcessResult
from open_bos_stream.stream.probe import StreamProbeService


class ProbeRunner:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0
        self.commands = []

    def run(self, command, **kwargs):
        self.calls += 1
        self.commands.append(command)
        return ProcessResult(
            command=tuple(command),
            returncode=0,
            stdout=json.dumps(self.payload),
            stderr="",
            duration=0.1,
        )


def test_probe_detects_implausible_fps_and_backwards_dts() -> None:
    runner = ProbeRunner({
        "streams": [{
            "codec_name": "h264",
            "width": 1280,
            "height": 720,
            "r_frame_rate": "1000/1",
            "avg_frame_rate": "30/1",
            "time_base": "1/90000",
            "has_b_frames": 2,
        }],
        "packets": [
            {"dts_time": "1.0", "size": "1000"},
            {"dts_time": "0.9", "size": "1000"},
        ],
    })
    probe = StreamProbeService(
        ConfigLoader().load(),
        runner,
        background=False,
    )

    status = probe.status(source_ready=True)

    assert status["available"] is True
    assert status["average_fps"] == 30
    assert status["backwards_dts"] == 1
    assert status["sample_bytes"] == 2000
    assert {
        warning["code"]
        for warning in status["warnings"]
    } == {
        "implausible_frame_rate",
        "non_monotonic_dts",
    }


def test_probe_calculates_bitrate_and_packet_timing() -> None:
    runner = ProbeRunner({
        "streams": [{
            "codec_name": "h264",
            "r_frame_rate": "25/1",
            "avg_frame_rate": "25/1",
            "time_base": "1/90000",
        }],
        "packets": [
            {"dts_time": "0.00", "size": "1000"},
            {"dts_time": "0.04", "size": "1000"},
            {"dts_time": "0.08", "size": "1000"},
        ],
    })
    probe = StreamProbeService(
        ConfigLoader().load(),
        runner,
        background=False,
    )

    status = probe.status(source_ready=True)

    assert status["bitrate_bps"] == 300_000
    assert status["packet_gaps"] == 0
    assert status["max_gap_ms"] == 40
    assert status["timing_jitter_ms"] < 0.001


def test_probe_result_is_cached() -> None:
    runner = ProbeRunner({"streams": [], "packets": []})
    probe = StreamProbeService(
        ConfigLoader().load(),
        runner,
        background=False,
    )

    probe.status(source_ready=True)
    probe.status(source_ready=True)

    assert runner.calls == 1
    assert "%+2" in runner.commands[0]
    assert StreamProbeService.CACHE_SECONDS == 60.0
