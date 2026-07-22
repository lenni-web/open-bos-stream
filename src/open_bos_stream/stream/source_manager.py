"""
Source Manager
"""

from __future__ import annotations

from open_bos_stream.core.models import (
    AppConfig,
    SourceConfig,
)


class SourceManager:

    def __init__(
        self,
    ) -> None:

        self._sources: list[
            SourceConfig
        ] = []

    def sources(
        self,
    ) -> list[SourceConfig]:

        return list(
            self._sources
        )

    def active_sources(
        self,
    ) -> list[SourceConfig]:

        return [

            source

            for source in self._sources

            if source.enabled

        ]

    def primary_source(
        self,
    ) -> SourceConfig | None:

        sources = self.active_sources()

        if not sources:

            return None

        return sources[0]

    def add(
        self,
        source: SourceConfig,
    ) -> None:

        self._sources.append(
            source,
        )

    def get(
        self,
        source_id: str,
    ) -> SourceConfig | None:

        for source in self._sources:

            if source.id == source_id:

                return source

        return None

    def enabled(
        self,
        source_id: str,
    ) -> bool:

        source = self.get(
            source_id,
        )

        return (

            source is not None

            and

            source.enabled

        )

    def enable(
        self,
        source_id: str,
    ) -> None:

        source = self.get(
            source_id,
        )

        if source:

            source.enabled = True

    def disable(
        self,
        source_id: str,
    ) -> None:

        source = self.get(
            source_id,
        )

        if source:

            source.enabled = False

    def remove(
        self,
        source_id: str,
    ) -> None:

        self._sources = [

            source

            for source in self._sources

            if source.id != source_id

        ]

    def clear(
        self,
    ) -> None:

        self._sources.clear()

    def has_sources(
        self,
    ) -> bool:

        return bool(
            self.active_sources()
        )

    def count(
        self,
    ) -> int:

        return len(
            self._sources
        )

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
    ) -> "SourceManager":

        manager = cls()

        #
        # Neue Konfiguration
        #
        if config.sources:

            for source in config.sources:

                if source.enabled:

                    manager.add(
                        source,
                    )

            return manager

        #
        # Legacy-Konfiguration
        #
        manager.add(

            SourceConfig(

                id="default",

                enabled=True,

                **config.input.model_dump(),

            )

        )

        return manager