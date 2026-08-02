from pathlib import Path
from types import SimpleNamespace

from open_bos_stream.recording.playback import RecordingPlaybackCache


def test_compatible_recording_is_cached(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "recording_test.mp4"
    source.write_bytes(b"original")
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"compatible")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(
        "open_bos_stream.recording.playback.subprocess.run",
        fake_run,
    )
    cache = RecordingPlaybackCache(tmp_path)

    first = cache.prepare(source)
    second = cache.prepare(source)

    assert first == second
    assert first.read_bytes() == b"compatible"
    assert len(commands) == 1
    assert ["-c:v", "libx264"] == commands[0][
        commands[0].index("-c:v"):commands[0].index("-c:v") + 2
    ]
    assert ["-movflags", "+faststart"] == commands[0][
        commands[0].index("-movflags"):commands[0].index("-movflags") + 2
    ]

    cache.remove(source)
    assert not first.exists()
