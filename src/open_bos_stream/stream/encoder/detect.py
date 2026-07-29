"""
FFmpeg Encoder Detection
"""

from __future__ import annotations

from open_bos_stream.core.process import ProcessRunner

from open_bos_stream.stream.encoder.factory import (
    EncoderFactory,
)

from open_bos_stream.stream.encoder.models import (
    EncoderInfo,
)


class EncoderDetector:
    def __init__(self, runner: ProcessRunner | None = None) -> None:
        self._runner = runner or ProcessRunner()

    def available(
        self,
    ) -> set[str]:

        result = self._runner.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-encoders",
            ],

            timeout=5,
        )

        encoders: set[str] = set()

        for line in result.stdout.splitlines():

            if not line.startswith(" V"):
                continue

            parts = line.split()

            if len(parts) < 2:
                continue

            if parts[1] == "=":
                continue

            encoders.add(
                parts[1],
            )

        encoders.add(
            "copy",
        )

        return encoders

    def supported(
        self,
        input_type: str,
    ) -> list[EncoderInfo]:

        available = self.available()

        result: list[EncoderInfo] = []

        for registration in EncoderFactory.available_for(
            input_type,
        ):

            result.append(

                EncoderInfo(

                    codec=registration.codec,

                    name=registration.name,

                    available=(
                        registration.codec in available
                    ),

                    hardware=registration.hardware,

                    transcodes=registration.transcodes,

                    options=registration.options,

                )

            )

        return result

    def supports(
        self,
        codec: str,
    ) -> bool:

        return codec in self.available()
