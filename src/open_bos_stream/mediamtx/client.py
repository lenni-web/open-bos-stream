"""
MediaMTX API Client.
"""

from __future__ import annotations

from typing import Any

import requests


class MediaMTXClient:
    """Einfacher Client für die MediaMTX Control API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:9997",
        timeout: float = 2.0,
    ) -> None:

        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def online(self) -> bool:
        """Prüft, ob die API erreichbar ist."""

        try:
            response = requests.get(
                f"{self._base_url}/v3/paths/list",
                timeout=self._timeout,
            )

            return response.status_code == 200

        except requests.RequestException:
            return False

    def paths(self) -> list[dict[str, Any]]:
        """Liefert alle bekannten Streams."""

        try:
            response = requests.get(
                f"{self._base_url}/v3/paths/list",
                timeout=self._timeout,
            )

            response.raise_for_status()

            return response.json().get("items", [])

        except requests.RequestException:
            return []

    def path(self, name: str) -> dict[str, Any] | None:
        """Liefert Informationen zu einem einzelnen Stream."""

        for path in self.paths():

            if path.get("name") == name:
                return path

        return None
