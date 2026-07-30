"""
MediaMTX Service
"""

from __future__ import annotations

from open_bos_stream.core.models import (
    MediaMTXStatus,
    StreamInfo,
)
from open_bos_stream.mediamtx.client import MediaMTXClient


class MediaMTXService:
    """Geschäftslogik für MediaMTX."""

    def __init__(self, client: MediaMTXClient) -> None:

        self._client = client

    # ---------------------------------------------------------
    # MediaMTX Status
    # ---------------------------------------------------------

    @staticmethod
    def _status_from_stream(
        path: str,
        stream: dict | None,
        online: bool,
    ) -> MediaMTXStatus:
        if not online:
            return MediaMTXStatus(
                online=False,
                publisher=False,
                path=path,
                readers=0,
            )

        if stream is None:
            return MediaMTXStatus(
                online=True,
                publisher=False,
                path=path,
                readers=0,
            )

        tracks = stream.get("tracks", [])
        tracks2 = stream.get("tracks2", [])

        codec = None
        width = 0
        height = 0

        if tracks:
            codec = tracks[0]

        if tracks2:

            props = tracks2[0].get("codecProps")
            if props is None:
                props = {}

            width = props.get(
                "width",
                0,
            )

            height = props.get(
                "height",
                0,
            )

        source = stream.get("source")

        if isinstance(source, dict):

            source = source.get(
                "type"
            )

        return MediaMTXStatus(
            online=True,
            publisher=True,
            path=path,
            readers=len(
                stream.get(
                    "readers",
                    [],
                )
            ),

            ready=stream.get(
                "ready",
                False,
            ),

            source=source,

            tracks=len(tracks),

            codec=codec,

            width=width,

            height=height,

            bytes_received=stream.get(
                "bytesReceived",
                0,
            ),

            bytes_sent=stream.get(
                "bytesSent",
                0,
            ),

            online_time=stream.get(
                "onlineTime"
            ),
        )

    def statuses(
        self,
        paths: list[str],
    ) -> dict[str, MediaMTXStatus]:
        """Mehrere Pfade mit nur einem MediaMTX-Listenabruf prüfen."""

        unique_paths = list(dict.fromkeys(paths))
        online = self._client.online()
        streams = {
            item.get("name"): item
            for item in self._client.paths()
            if item.get("name")
        } if online else {}

        return {
            path: self._status_from_stream(
                path,
                streams.get(path),
                online,
            )
            for path in unique_paths
        }

    def status(self, path: str) -> MediaMTXStatus:
        """Status eines Streams zurückgeben."""

        return self.statuses([path])[path]

    # ---------------------------------------------------------
    # Stream Information
    # ---------------------------------------------------------

    def stream_info(self, path: str) -> StreamInfo:
        """Informationen für das Dashboard liefern."""

        status = self.status(path)

        if not status.online:

            return StreamInfo(
                online=False,
                protocol="offline",
                viewers=0,
                recording=False,
            )

        protocol = (
            "rtsp"
            if status.publisher
            else "offline"
        )

        return StreamInfo(
            online=status.publisher,
            protocol=protocol,
            viewers=status.readers,
            recording=False,
        )
