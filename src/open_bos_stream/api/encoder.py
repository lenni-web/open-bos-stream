"""
Encoder API
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
)

from open_bos_stream.api.models import (
    EncoderRequest,
)

from open_bos_stream.stream.encoder.detect import (
    EncoderDetector,
)

from open_bos_stream.stream.encoder.factory import (
    EncoderFactory,
)

from open_bos_stream.stream.encoder.models import (
    EncoderInfo,
)

from open_bos_stream.stream.inputs import (
    registry,
)

router = APIRouter(

    prefix="/encoder",

    tags=["Encoder"],

)


@router.post("/")
async def encoders(
    source: EncoderRequest,
):

    detector = EncoderDetector()

    builder = registry.get(
        source.type,
    )

    input_formats = builder.output_formats(
        source,
    )

    result: list[EncoderInfo] = []

    for registration in EncoderFactory.available_for(
        source.type,
        input_formats,
    ):

        result.append(

            EncoderInfo(
                codec=registration.codec,
                name=registration.name,
                available=detector.supports(
                    registration.codec,
                ),
                hardware=registration.hardware,
                transcodes=registration.transcodes,
                options=registration.options,
            )
        )

    return result