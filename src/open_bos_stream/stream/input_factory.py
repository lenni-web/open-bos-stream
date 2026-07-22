"""
Input Factory
"""

from __future__ import annotations

from open_bos_stream.core.models import (
    SourceConfig,
)

from open_bos_stream.stream.inputs import (
    registry,
)


class InputFactory:

    @staticmethod
    def create(
        source: SourceConfig,
    ):

        builder = registry.get(
            source.type,
        )

        if builder is None:

            raise ValueError(

                f"Unsupported input type: {source.type}"

            )

        return builder
