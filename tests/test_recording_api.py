import asyncio

import pytest
from fastapi import HTTPException

from open_bos_stream.api import recording


@pytest.mark.parametrize(
    "endpoint",
    [
        recording.play,
        recording.download,
    ],
)
def test_missing_recording_returns_404(
    monkeypatch: pytest.MonkeyPatch,
    endpoint,
) -> None:
    monkeypatch.setattr(
        recording.recording_library,
        "get_file",
        lambda _filename: None,
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(endpoint("missing.mp4"))

    assert error.value.status_code == 404
    assert error.value.detail == "Aufnahme nicht gefunden."
