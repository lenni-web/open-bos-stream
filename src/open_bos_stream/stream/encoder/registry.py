"""
Encoder Registry Model
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from open_bos_stream.stream.encoder.options import (
    EncoderOption,
)

@dataclass(slots=True)
class EncoderRegistration:

    codec: str

    name: str

    encoder: type

    hardware: bool = False

    transcodes: bool = True

    supported_inputs: list[str] | None = None

    options: list[EncoderOption] = field(

        default_factory=list,

    )