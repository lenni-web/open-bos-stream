"""
System Information Service
"""

from __future__ import annotations

import socket
from pathlib import Path
import platform
import fcntl
import struct
from open_bos_stream.version import (
    APP_NAME,
    VERSION,
)
from open_bos_stream.core.process import ProcessRunner
from open_bos_stream.core.models import (
    ApplicationInfo,
    HardwareInfo,
    NetworkInfo,
    OperatingSystemInfo,
    RuntimeInfo,
    SystemInfo,
)

class SystemInfoService:
    def __init__(self, runner: ProcessRunner | None = None) -> None:
        self._runner = runner or ProcessRunner()

    def _distribution(self) -> str:

        try:
            return (
                self._runner.run(
                    ["lsb_release", "-ds"],
                    timeout=3,
                ).stdout
                .strip()
                .strip('"')
            )

        except Exception:
            return platform.system()

    def _hardware(self) -> str:

        try:
            return (
                Path("/proc/device-tree/model")
                .read_text()
                .strip("\x00")
                .strip()
            )

        except Exception:
            return "Unknown"

    def _ffmpeg_version(self) -> str:

        try:
            output = self._runner.run(
                ["ffmpeg", "-version"],
                timeout=3,
            ).stdout

            return output.splitlines()[0].replace(
                "ffmpeg version ",
                "",
            )

        except Exception:
            return "Unknown"

    def _interface(self) -> str:

        active = []

        try:

            for path in Path("/sys/class/net").iterdir():

                if path.name == "lo":
                    continue

                try:

                    state = (
                        path.joinpath("operstate")
                        .read_text()
                        .strip()
                    )

                    if state == "up":
                        active.append(path.name)

                except Exception:
                    continue

        except Exception:
            return "Unknown"

        #
        # Ethernet bevorzugen
        #
        if "eth0" in active:
            return "eth0"

        if active:
            return active[0]

        return "Unknown"

    def _ipv4(self, interface: str) -> str:

        try:

            sock = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM,
            )

            request = struct.pack(
                "256s",
                interface.encode()[:15],
            )

            response = fcntl.ioctl(
                sock.fileno(),
                0x8915,  # SIOCGIFADDR
                request,
            )

            return socket.inet_ntoa(
                response[20:24]
            )

        except Exception:
            return "Unknown"

    def _mac(self, interface: str) -> str:

        try:

            return (
                Path(
                    f"/sys/class/net/{interface}/address"
                )
                .read_text()
                .strip()
            )

        except Exception:
            return "Unknown"

    def info(self) -> SystemInfo:

        interface = self._interface()

        return SystemInfo(

            application=ApplicationInfo(
                name=APP_NAME,
                version=VERSION,
            ),

            hardware=HardwareInfo(
                model=self._hardware(),
                architecture=platform.machine(),
            ),

            operating_system=OperatingSystemInfo(
                system=platform.system(),
                distribution=self._distribution(),
                kernel=platform.release(),
            ),

            runtime=RuntimeInfo(
                python=platform.python_version(),
                ffmpeg=self._ffmpeg_version(),
            ),

            network=NetworkInfo(
                hostname=socket.gethostname(),
                interface=interface,
                ipv4=self._ipv4(interface),
                mac=self._mac(interface),
            ),

        )
