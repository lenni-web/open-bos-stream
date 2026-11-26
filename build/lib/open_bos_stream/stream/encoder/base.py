"""
Encoder Basisklasse
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from open_bos_stream.stream.video_formats import (
    VideoFormat,
)

from open_bos_stream.core.models import (
    EncoderConfig,
)

from open_bos_stream.stream.encoder.registry import (
    EncoderRegistration,
)


class Encoder(ABC):
    """Basisklasse für alle Encoder."""

    codec: str = ""

    def __init__(
        self,
        config: EncoderConfig,
        registration: EncoderRegistration,
    ) -> None:

        self.config = config

        self.registration = registration

    @classmethod
    def supports(
        cls,
        formats: list[VideoFormat],
    ) -> bool:

        return True

    @abstractmethod
    def build(
        self,
    ) -> list[str]:
        """Erzeugt die FFmpeg-Encoderargumente."""

    def build_ffmpeg_args(
        self,
    ) -> list[str]:

        args: list[str] = []

        for option in self.registration.options:

            if not option.ffmpeg:

                continue

            value = getattr(
                self.config,
                option.id,
                None,
            )

            if value in (
                None,
                "",
            ):

                continue

            args.extend(

                [

                    option.ffmpeg,

                    str(value),

                ]

            )

        return args

    def build_filter_args(
        self,
    ) -> list[str]:

        filters: list[str] = []

        for option in self.registration.options:

            if not option.ffmpeg_filter:

                continue

            value = getattr(
                self.config,
                option.id,
                None,
            )

            if value in (
                None,
                "",
            ):

                continue

            filters.append(
                f"{option.ffmpeg_filter}={value}"
            )

        return filters

    def build_args(
        self,
        *,
        gop: bool = False,
        extra_args: list[str] | None = None,
    ) -> list[str]:
        """Erzeugt ausschließlich FFmpeg-Encoderargumente."""

        args = [
            "-c:v",
            self.codec,
        ]

        args.extend(
            self.build_ffmpeg_args()
        )

        args.extend(
            [
                "-maxrate",
                self.config.bitrate,
                "-bufsize",
                self.config.bitrate,
            ]
        )

        if gop:
            args.extend(
                [
                    "-g",
                    str(self.config.gop),
                ]
            )

        if extra_args:
            args.extend(extra_args)

        return args


    def build_filters(
        self,
    ) -> list[str]:
        """Erzeugt ausschließlich FFmpeg-Filter."""

        return self.build_filter_args()
