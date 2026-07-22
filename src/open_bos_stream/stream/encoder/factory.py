"""
Encoder Factory
"""

from __future__ import annotations

from open_bos_stream.core.models import (
    EncoderConfig,
)

from open_bos_stream.stream.video_formats import (
    VideoFormat,
)

from open_bos_stream.stream.encoder.option_factory import (
    bitrate_option,
    pixel_format_option,
    preset_option,
    tune_option,
)

from open_bos_stream.stream.encoder.registry import (
    EncoderRegistration,
)

from open_bos_stream.stream.encoder.validator import (
    EncoderValidator,
)

class EncoderFactory:

    _registry: dict[str, EncoderRegistration] = {}

    @classmethod
    def register(
        cls,
        registration: EncoderRegistration,
    ) -> None:

        cls._registry[
            registration.codec
        ] = registration

    @classmethod
    def create(
        cls,
        config: EncoderConfig,
    ):

        entry = cls._registry.get(
            config.codec
        )

        if entry is None:

            raise ValueError(
                f"Unbekannter Encoder: {config.codec}"
            )

        config = EncoderValidator.validate(
            config,
            entry,
        )

        return entry.encoder(

            config,

            entry,

        )

    @classmethod
    def supported(
        cls,
    ) -> list[EncoderRegistration]:

        return list(
            cls._registry.values()
        )

    @classmethod
    def available_for(
        cls,
        input_type: str,
        input_formats: list[VideoFormat],
    ) -> list[EncoderRegistration]:

        encoders: list[EncoderRegistration] = []

        for registration in cls._registry.values():

            #
            # Input-Typ prüfen
            #
            if (
                registration.supported_inputs
                and input_type not in registration.supported_inputs
            ):
                continue

            #
            # Encoder entscheidet selbst,
            # ob er das Eingangsformat unterstützt.
            #
            if not registration.encoder.supports(

                input_formats,

            ):

                continue

            encoders.append(
                registration,
            )

        return encoders

    @classmethod
    def get(
        cls,
        codec: str,
    ) -> EncoderRegistration | None:

        return cls._registry.get(
            codec
        )

from open_bos_stream.stream.encoder.copy import (
    CopyEncoder,
)

from open_bos_stream.stream.encoder.h264_v4l2m2m import (
    H264V4L2M2MEncoder,
)

from open_bos_stream.stream.encoder.x264 import (
    X264Encoder,
)

from open_bos_stream.stream.encoder.x265 import (
    X265Encoder,
)

EncoderFactory.register(

    EncoderRegistration(

        codec="copy",

        name="Passthrough (Codec unverändert)",

        encoder=CopyEncoder,

        transcodes=False,

        supported_inputs=[
            "rtmp",
            "rtsp",
            "srt",
            "udp",
            "http",
            "hls",
        ],

    )

)

EncoderFactory.register(

    EncoderRegistration(

        codec="libx264",

        name="H.264 (Software)",

        encoder=X264Encoder,

        options=[

            bitrate_option(),

            pixel_format_option(
                choices=[
                    "yuv420p",
                ],
            ),

            preset_option(
                choices=[
                    "ultrafast",
                    "superfast",
                    "veryfast",
                    "faster",
                    "fast",
                    "medium",
                    "slow",
                    "slower",
                    "veryslow",
                ],
                default="ultrafast",
            ),

            tune_option(
                choices=[
                    "film",
                    "animation",
                    "grain",
                    "stillimage",
                    "fastdecode",
                    "zerolatency",
                ],
                default="zerolatency",
            ),

        ]

    )

)

EncoderFactory.register(

    EncoderRegistration(

        codec="h264_v4l2m2m",

        name="H.264 (Raspberry Pi Hardware)",

        encoder=H264V4L2M2MEncoder,

        hardware=True,

        options=[

            bitrate_option(),

            pixel_format_option(
                choices=[
                    "yuv420p",
                    "nv12",
                ],
                hardware=True,
            ),

        ]

    )

)

EncoderFactory.register(

    EncoderRegistration(

        codec="libx265",

        name="H.265 / HEVC",

        encoder=X265Encoder,

        options=[

            bitrate_option(),

            pixel_format_option(
                choices=[
                    "yuv420p",
                    "yuv420p10le",
                ],
            ),

        ]

    )

)