import sys

import pytest

from open_bos_stream.core.process import (
    ProcessExecutionError,
    ProcessRunner,
)


def test_process_runner_captures_result() -> None:
    result = ProcessRunner().run(
        [sys.executable, "-c", "print('ready')"],
        timeout=2,
    )

    assert result.ok is True
    assert result.stdout.strip() == "ready"
    assert result.duration >= 0


def test_process_runner_raises_consistent_error() -> None:
    with pytest.raises(ProcessExecutionError) as error:
        ProcessRunner().run(
            [sys.executable, "-c", "raise SystemExit(3)"],
            timeout=2,
            check=True,
        )

    assert error.value.result.returncode == 3


def test_process_runner_masks_stream_target_in_logs() -> None:
    safe = ProcessRunner._safe_command(
        (
            "ffmpeg",
            "-f",
            "flv",
            "rtmp://user:password@example.test/live/secret-key",
        )
    )

    assert "password" not in safe
    assert "secret-key" not in safe
    assert safe.endswith("/live/***")
