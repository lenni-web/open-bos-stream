"""
Input Builder Registry
"""

from __future__ import annotations

from .base import InputBuilder


class InputRegistry:

    def __init__(self) -> None:

        self._builders: dict[
            str,
            InputBuilder,
        ] = {}

    def register(
        self,
        builder: InputBuilder,
    ) -> None:

        self._builders[
            builder.type
        ] = builder

    def get(
        self,
        name: str,
    ) -> InputBuilder:

        return self._builders[name]

    def all(
        self,
    ) -> list[InputBuilder]:

        return list(
            self._builders.values()
        )

    def metadata(
        self,
    ) -> list[dict]:

        items: list[dict] = []

        for builder in self.all():

            fields = builder.fields

            if hasattr(
                builder,
                "metadata_fields",
            ):

                fields = builder.metadata_fields()

            items.append(

                {

                    "type": builder.type,

                    "name": builder.name,

                    "fields": fields,

                    "capability_fields": builder.capability_fields(),

                }

            )

        return items

registry = InputRegistry()
