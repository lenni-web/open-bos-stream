from __future__ import annotations

import re
from open_bos_stream.core.process import ProcessRunner

from open_bos_stream.stream.inputs.v4l2_device import (
    V4L2Device,
)

from open_bos_stream.stream.video_formats import (
    VideoFormat,
)

from open_bos_stream.stream.video_formats import (
    VideoFormat,
)

class V4L2Detector:
    _runner = ProcessRunner()

    @staticmethod
    def devices(
    ) -> list[V4L2Device]:

        result = V4L2Detector._runner.run(

            [
                "v4l2-ctl",
                "--list-devices",
            ],

            timeout=5,

        )

        if result.returncode != 0:

            return []

        devices: list[V4L2Device] = []

        current_name = ""

        for line in result.stdout.splitlines():

            if not line.strip():

                continue

            if not line.startswith("\t"):

                current_name = line.rstrip(":")

                continue

            path = line.strip()

            if not path.startswith("/dev/video"):

                continue

            capabilities = V4L2Detector.device_capabilities(
                path,
            )

            if "Video Capture" not in capabilities:

                continue

            devices.append(

                V4L2Device(

                    path=path,

                    name=current_name,

                    driver=V4L2Detector.driver(
                        path,
                    ),

                    capabilities=capabilities,

                    formats=[

                        VideoFormat(fmt)

                        for fmt in V4L2Detector.formats(
                            path,
                        )

                    ],

                )

            )

        return devices

    @staticmethod
    def selectable_devices(
    ) -> list[V4L2Device]:

        ignored_drivers = {

            "bcm2835-isp",

            "bcm2835-codec",

            "rpi-hevc-dec",

        }

        return [

            device

            for device in V4L2Detector.devices()

            if (

                device.path.startswith(
                    "/dev/video",
                )

                and device.driver
                not in ignored_drivers

            )

        ]

    @staticmethod
    def capabilities(
        device: str,
    ) -> list[str]:

        result = V4L2Detector._runner.run(

            [
                "v4l2-ctl",
                "-d",
                device,
                "--all",
            ],

            timeout=5,

        )

        if result.returncode != 0:

            return []

        capabilities: list[str] = []

        collect = False

        for line in result.stdout.splitlines():

            stripped = line.strip()

            if stripped.startswith("Capabilities"):

                collect = True

                continue

            if stripped.startswith("Device Caps"):

                collect = True

                continue

            if collect:

                if not stripped:

                    break

                if ":" in stripped:

                    continue

                capabilities.append(
                    stripped,
                )

        return capabilities

    @staticmethod
    def device_capabilities(
        device: str,
    ) -> list[str]:

        result = V4L2Detector._runner.run(

            [
                "v4l2-ctl",
                "-d",
                device,
                "--all",
            ],

            timeout=5,

        )

        if result.returncode != 0:

            return []

        caps: list[str] = []

        in_device_caps = False

        for line in result.stdout.splitlines():

            stripped = line.strip()

            if stripped.startswith(
                "Device Caps"
            ):

                in_device_caps = True

                continue

            if not in_device_caps:

                continue

            if not stripped:

                break

            if ":" in stripped:

                break

            caps.append(
                stripped,
            )

        return caps

    @staticmethod
    def driver(
        device: str,
    ) -> str:

        result = V4L2Detector._runner.run(

            [
                "v4l2-ctl",
                "-d",
                device,
                "--all",
            ],

            timeout=5,

        )

        if result.returncode != 0:

            return ""

        for line in result.stdout.splitlines():

            if line.strip().startswith(
                "Driver name"
            ):

                return line.split(
                    ":",
                    1,
                )[1].strip()

        return ""

    @staticmethod
    def is_capture_device(
        device: str,
    ) -> bool:

        driver = V4L2Detector.driver(
            device,
        )

        return driver not in (

            "bcm2835-isp",

            "bcm2835-codec",

            "rpi-hevc-dec",

        )

    @staticmethod
    def formats(
        device: str,
    ) -> list[str]:

        result = V4L2Detector._runner.run(

            [
                "v4l2-ctl",
                "-d",
                device,
                "--list-formats-ext",
            ],

            timeout=5,

        )

        if result.returncode != 0:

            return [
                "mjpeg",
            ]

        mapping = {

            "MJPG": VideoFormat.MJPEG,

            "YUYV": VideoFormat.YUYV422,

            "H264": VideoFormat.H264,

            "HEVC": VideoFormat.HEVC,

        }

        formats: list[VideoFormat] = []

        for line in result.stdout.splitlines():

            match = re.search(

                r"'([A-Z0-9]+)'",

                line,

            )

            if not match:

                continue

            fourcc = match.group(1)

            fmt = mapping.get(
                fourcc,
            )

            if (
                fmt is not None
                and fmt not in formats
            ):

                formats.append(
                    fmt,
                )

        if not formats:

            formats.append(
                VideoFormat.MJPEG,
            )

        return [

            fmt.value

            for fmt in formats

        ]
