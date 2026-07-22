"""
Device Manager
"""

from __future__ import annotations

from .v4l2_detect import (
    V4L2Detector,
)

from .v4l2_device import (
    V4L2Device,
)


class DeviceManager:

    _video_devices: list[V4L2Device] = []

    @classmethod
    def refresh(
        cls,
    ) -> None:

        cls._video_devices = (

            V4L2Detector.selectable_devices()

        )

    @classmethod
    def video_devices(
        cls,
    ) -> list[V4L2Device]:

        if not cls._video_devices:

            cls.refresh()

        return list(
            cls._video_devices
        )

    @classmethod
    def video_device(
        cls,
        path: str,
    ) -> V4L2Device | None:

        for device in cls.video_devices():

            if device.path == path:

                return device

        return None