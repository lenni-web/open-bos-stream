import sys

import pytest

from open_bos_stream.stream_output.process import StreamOutputProcess


def test_output_process_surfaces_stderr_on_early_exit() -> None:
    process = StreamOutputProcess()

    with pytest.raises(RuntimeError, match="SRT handshake failed"):
        process.start([
            sys.executable,
            "-c",
            (
                "import sys; "
                "print('SRT handshake failed', file=sys.stderr); "
                "raise SystemExit(1)"
            ),
        ])

    assert process.last_error == "SRT handshake failed"
