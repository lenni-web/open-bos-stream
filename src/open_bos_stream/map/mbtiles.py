from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class MBTilesError(RuntimeError):
    """Raised when an MBTiles database cannot be opened or read."""


@dataclass(frozen=True, slots=True)
class MBTilesMetadata:
    name: str | None = None
    description: str | None = None
    attribution: str | None = None
    tile_format: str | None = None
    min_zoom: int | None = None
    max_zoom: int | None = None
    bounds: tuple[float, float, float, float] | None = None
    center: tuple[float, float, int] | None = None


@dataclass(frozen=True, slots=True)
class MapTile:
    data: bytes
    media_type: str


class MBTilesProvider:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def validate(self) -> None:
        if not self.path.is_file():
            raise MBTilesError(
                f"MBTiles file does not exist: {self.path}"
            )

        try:
            with sqlite3.connect(self.path) as connection:
                rows = connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type IN ('table', 'view')
                    """
                ).fetchall()
        except sqlite3.Error as exc:
            raise MBTilesError(
                f"Could not open MBTiles database: {self.path}"
            ) from exc

        objects = {
            row[0]
            for row in rows
        }

        required = {
            "metadata",
            "tiles",
        }

        missing = sorted(
            required - objects
        )

        if missing:
            raise MBTilesError(
                "Invalid MBTiles database; "
                f"missing tables or views: {', '.join(missing)}"
            )

    def get_metadata(self) -> MBTilesMetadata:
        self.validate()

        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT name, value
                    FROM metadata
                    """
                ).fetchall()
        except sqlite3.Error as exc:
            raise MBTilesError(
                f"Unable to read MBTiles metadata: {self.path}"
            ) from exc

        values = {
            str(row["name"]): str(row["value"])
            for row in rows
        }

        return MBTilesMetadata(
            name=values.get("name"),
            description=values.get("description"),
            attribution=values.get("attribution"),
            tile_format=values.get("format"),
            min_zoom=self._parse_int(
                values.get("minzoom")
            ),
            max_zoom=self._parse_int(
                values.get("maxzoom")
            ),
            bounds=self._parse_bounds(
                values.get("bounds")
            ),
            center=self._parse_center(
                values.get("center")
            ),
        )

    def get_tile(
        self,
        zoom: int,
        x: int,
        y: int,
    ) -> MapTile | None:
        if zoom < 0:
            return None

        if x < 0 or y < 0:
            return None

        max_coordinate = (1 << zoom) - 1

        if x > max_coordinate or y > max_coordinate:
            return None

        # Webkarten verwenden üblicherweise XYZ-Koordinaten.
        # MBTiles speichert die Y-Achse nach dem TMS-Schema.
        tms_y = max_coordinate - y

        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT tile_data
                    FROM tiles
                    WHERE zoom_level = ?
                      AND tile_column = ?
                      AND tile_row = ?
                    """,
                    (
                        zoom,
                        x,
                        tms_y,
                    ),
                ).fetchone()
        except sqlite3.Error as exc:
            raise MBTilesError(
                f"Unable to read tile {zoom}/{x}/{y}"
            ) from exc

        if row is None:
            return None

        data = bytes(row["tile_data"])
        media_type = self._detect_media_type(data)

        return MapTile(
            data=data,
            media_type=media_type,
        )

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(
                f"file:{self.path}?mode=ro",
                uri=True,
                timeout=5.0,
            )
        except sqlite3.Error as exc:
            raise MBTilesError(
                f"Unable to open MBTiles database: {self.path}"
            ) from exc

        connection.row_factory = sqlite3.Row

        return connection

    @staticmethod
    def _detect_media_type(data: bytes) -> str:
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"

        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"

        if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return "image/webp"

        # Vektor-Tiles werden normalerweise als gzip-komprimierte
        # Protocol-Buffer-Daten gespeichert.
        if data.startswith(b"\x1f\x8b"):
            return "application/vnd.mapbox-vector-tile"

        return "application/octet-stream"

    @staticmethod
    def _parse_int(
        value: str | None,
    ) -> int | None:
        if value is None:
            return None

        try:
            return int(value)
        except ValueError:
            return None

    @staticmethod
    def _parse_bounds(
        value: str | None,
    ) -> tuple[float, float, float, float] | None:
        parsed = MBTilesProvider._parse_csv_numbers(
            value=value,
            expected_length=4,
        )

        if parsed is None:
            return None

        west, south, east, north = parsed

        return (
            west,
            south,
            east,
            north,
        )

    @staticmethod
    def _parse_center(
        value: str | None,
    ) -> tuple[float, float, int] | None:
        parsed = MBTilesProvider._parse_csv_numbers(
            value=value,
            expected_length=3,
        )

        if parsed is None:
            return None

        longitude, latitude, zoom = parsed

        return (
            longitude,
            latitude,
            int(zoom),
        )

    @staticmethod
    def _parse_csv_numbers(
        value: str | None,
        expected_length: int,
    ) -> tuple[Any, ...] | None:
        if value is None:
            return None

        parts = [
            part.strip()
            for part in value.split(",")
        ]

        if len(parts) != expected_length:
            return None

        try:
            return tuple(
                float(part)
                for part in parts
            )
        except ValueError:
            return None