from __future__ import annotations

import json
from pathlib import Path

from open_bos_stream.core.models import MapConfig
from open_bos_stream.map.mbtiles import (
    MBTilesMetadata,
    MBTilesProvider,
    MapTile,
)


class MapService:
    def __init__(
        self,
        config: MapConfig,
    ) -> None:
        self._config = config
        self._map_directory = Path(
            config.path
        )

    def validate(self) -> None:
        if not self._map_directory.exists():
            raise RuntimeError(
                "Map directory does not exist: "
                f"{self._map_directory}"
            )

        if not self._map_directory.is_dir():
            raise RuntimeError(
                "Map path is not a directory: "
                f"{self._map_directory}"
            )

        default_map = self.default_map()

        if default_map is not None:
            self._provider(
                default_map
            ).validate()

    def list_maps(self) -> list[str]:
        if not self._map_directory.exists():
            return []

        if not self._map_directory.is_dir():
            return []

        return sorted(
            path.stem
            for path in self._map_directory.glob(
                "*.mbtiles"
            )
            if path.is_file()
        )

    def default_map(self) -> str | None:
        maps = self.list_maps()

        if not maps:
            return None

        configured_default = (
            self._config.default
        )

        if configured_default is not None:
            normalized_default = (
                self._normalize_map_name(
                    configured_default
                )
            )

            if normalized_default in maps:
                return normalized_default

            raise RuntimeError(
                "Configured default map does not exist: "
                f"{configured_default}"
            )

        return maps[0]

    def metadata(
        self,
        name: str,
    ) -> MBTilesMetadata:
        return self._provider(
            name
        ).get_metadata()

    def tile(
        self,
        name: str,
        z: int,
        x: int,
        y: int,
    ) -> MapTile | None:
        return self._provider(
            name
        ).get_tile(
            zoom=z,
            x=x,
            y=y,
        )

    def styles(self) -> list[str]:
        styles_path = (
            Path(__file__).parent
            / "styles"
        )

        return sorted(
            path.stem
            for path in styles_path.glob("*.json")
            if path.is_file()
        )

    def style(
        self,
        tile_url: str,
        name: str | None = None,
        style_name: str = "basic",
    ) -> dict:
        if name is None:
            name = self.default_map()

        if name is None:
            raise RuntimeError(
                "No default map configured."
            )

        if not style_name.isidentifier():
            raise ValueError(
                f"Invalid style name: {style_name}"
            )

        metadata = self.metadata(name)

        style_path = (
            Path(__file__).parent
            / "styles"
            / f"{style_name}.json"
        )

        with style_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            style = json.load(file)

        style["sources"]["openbos"] = {
            "type": "vector",
            "tiles": [
                tile_url,
            ],
        }

        if metadata.min_zoom is not None:
            style["sources"]["openbos"]["minzoom"] = (
                metadata.min_zoom
            )

        if metadata.max_zoom is not None:
            style["sources"]["openbos"]["maxzoom"] = (
                metadata.max_zoom
            )

        if metadata.name:
            style["name"] = metadata.name

        if metadata.attribution:
            style["sources"]["openbos"]["attribution"] = (
                metadata.attribution
            )

        if metadata.bounds:
            style["bounds"] = list(
                metadata.bounds
            )

        if metadata.center:
            longitude, latitude, zoom = (
                metadata.center
            )

            style["center"] = [
                9.52972,
                53.56389,
            ]
            style["zoom"] = 14

        return style

    def map_path(
        self,
        name: str,
    ) -> Path:
        normalized_name = (
            self._normalize_map_name(
                name
            )
        )

        path = (
            self._map_directory
            / f"{normalized_name}.mbtiles"
        )

        try:
            path.relative_to(
                self._map_directory
            )
        except ValueError as exc:
            raise ValueError(
                "Invalid map name."
            ) from exc

        if not path.exists():
            raise FileNotFoundError(
                f"Map does not exist: {normalized_name}"
            )

        if not path.is_file():
            raise FileNotFoundError(
                f"Map is not a file: {normalized_name}"
            )

        return path

    def _provider(
        self,
        name: str,
    ) -> MBTilesProvider:
        return MBTilesProvider(
            self.map_path(name)
        )

    @staticmethod
    def _normalize_map_name(
        name: str,
    ) -> str:
        normalized_name = (
            name.strip()
        )

        if normalized_name.endswith(
            ".mbtiles"
        ):
            normalized_name = (
                normalized_name[
                    :-len(".mbtiles")
                ]
            )

        if not normalized_name:
            raise ValueError(
                "Map name must not be empty."
            )

        if (
            "/" in normalized_name
            or "\\" in normalized_name
            or normalized_name in {
                ".",
                "..",
            }
        ):
            raise ValueError(
                "Invalid map name."
            )

        return normalized_name

    def glyph(
        self,
        fontstack: str,
        glyph_range: str,
    ) -> bytes:
        glyph_path = (
            Path(__file__).parent
            / "glyphs"
            / fontstack
            / glyph_range
        )

        try:
            glyph_path.relative_to(
                Path(__file__).parent / "glyphs"
            )
        except ValueError as exc:
            raise ValueError(
                "Invalid glyph path."
            ) from exc

        if not glyph_path.is_file():
            raise FileNotFoundError(
                f"Glyph not found: {fontstack}/{glyph_range}"
            )

        return glyph_path.read_bytes()

    def layers(self) -> list[str]:
        layers_path = (
            Path(__file__).parent
            / "layers"
        )

        return sorted(
            path.stem
            for path in layers_path.glob("*.geojson")
            if path.is_file()
        )

    def layer(self, name: str) -> dict:
        if not name.isidentifier():
            raise ValueError(
                f"Invalid layer name: {name}"
            )

        layer_path = (
            Path(__file__).parent
            / "layers"
            / f"{name}.geojson"
        )

        with layer_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)
