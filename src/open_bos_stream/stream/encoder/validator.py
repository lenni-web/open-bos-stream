"""
Encoder Configuration Validator
"""

from __future__ import annotations

from open_bos_stream.core.models import (
    EncoderConfig,
)

from open_bos_stream.stream.encoder.registry import (
    EncoderRegistration,
)

class EncoderValidator:

    @classmethod
    def validate(
        cls,
        config: EncoderConfig,
        registration: EncoderRegistration,
    ) -> EncoderConfig:

        for option in registration.options:

            value = getattr(
                config,
                option.id,
                None,
            )

            #
            # Default übernehmen
            #

            if (
                value is None
                or value == ""
            ):

                setattr(
                    config,
                    option.id,
                    option.default,
                )

                value = option.default

            #
            # Pflichtfeld
            #

            if (
                option.required
                and not value
            ):

                raise ValueError(
                    f"'{option.id}' is required."
                )

            #
            # Select validieren
            #

            if (
                option.type == "select"
                and option.choices
            ):

                if value not in option.choices:

                    raise ValueError(

                        f"Invalid value '{value}' "
                        f"for '{option.id}'."

                    )

        return config