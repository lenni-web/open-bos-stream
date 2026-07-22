"""
Basisklasse für alle Input-Builder.
"""

from __future__ import annotations

from abc import (
    ABC,
    abstractmethod,
)

from open_bos_stream.core.models import (
    SourceConfig,
)

from open_bos_stream.stream.video_formats import (
    VideoFormat,
)
from typing import Protocol

class InputDescription(
    Protocol,
):
    type: str
    format: str | None

class InputBuilder(ABC):

    #
    # Eindeutiger Typ
    #
    type: str = ""

    #
    # Anzeigename
    #
    name: str = ""

    #
    # Beschreibung der Eingabefelder
    #
    fields: list[dict] = []

    def output_formats(
        self,
        source: InputDescription,
    ) -> list[VideoFormat]:
        """
        Liefert die Videoformate,
        die dieser Input erzeugt.
        """

        try:

            return [

                VideoFormat(
                    source.format,
                )

            ]

        except Exception:

            return []

    def validate(
        self,
        source: SourceConfig,
    ) -> None:

        return

    def capability_fields(
        self,
    ) -> list[str]:

        return []

    def validate(
        self,
        source: SourceConfig,

    ) -> None:

        """
        Prüft die Eingabekonfiguration.
        Überschreiben, falls der Input spezielle
        Anforderungen hat.
        """

        return

    @abstractmethod
    def build(
        self,
        source: SourceConfig,
    ) -> list[str]:
        """
        Erzeugt die FFmpeg-Parameter
        für diesen Input.
        """
        ...