"""
Encoder Option Factory
"""

from __future__ import annotations

from open_bos_stream.stream.encoder.options import (
    EncoderOption,
)

def bitrate_option() -> EncoderOption:

    return EncoderOption(

        id="bitrate",

        label="Bitrate",

        default="8M",

        ffmpeg="-b:v",

    )

def pixel_format_option(
    *,
    choices: list[str],
    hardware: bool = False,
) -> EncoderOption:

    return EncoderOption(

        id="pixel_format",

        label="Pixelformat",

        type="select",

        default=choices[0],

        choices=choices,

        ffmpeg_filter=(
            "format"
            if hardware
            else ""
        ),

        ffmpeg=(
            ""
            if hardware
            else "-pix_fmt"
        ),

    )


def preset_option(
    choices: list[str],
    default: str,
) -> EncoderOption:

    return EncoderOption(

        id="preset",

        label="Preset",

        type="select",

        default=default,

        choices=choices,

        ffmpeg="-preset",

    )


def tune_option(
    choices: list[str],
    default: str,
) -> EncoderOption:

    return EncoderOption(

        id="tune",

        label="Tune",

        type="select",

        default=default,

        choices=choices,

        ffmpeg="-tune",

    )