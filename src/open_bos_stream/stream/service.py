"""
Streaming Service

Steuert den Stream über den systemd-Service
'open-bos-streamer.service'.
"""

from __future__ import annotations

import subprocess
import subprocess
import time

from open_bos_stream.core.models import StreamStatus

class StreamService:

    SERVICE = "open-bos-streamer.service"

    @property
    def running(self) -> bool:

        result = subprocess.run(
            [
                "systemctl",
                "is-active",
                "--quiet",
                self.SERVICE,
            ]
        )

        return result.returncode == 0

    @property
    def pid(self) -> int | None:

        result = subprocess.run(
            [
                "systemctl",
                "show",
                self.SERVICE,
                "--property=MainPID",
                "--value",
            ],
            capture_output=True,
            text=True,
        )

        pid = result.stdout.strip()

        if pid in ("", "0"):
            return None

        return int(pid)

    def start(self) -> bool:

        subprocess.run(
            [
                "sudo",
                "systemctl",
                "start",
                self.SERVICE,
            ],
            check=True,
        )

        time.sleep(1)

        if not self.running:

            error = self.last_error()

            raise RuntimeError(
                error or
                "Unable to start stream service."
            )

        return True

    def last_error(self) -> str | None:

        result = subprocess.run(
            [
                "journalctl",
                "-u",
                self.SERVICE,
                "-n",
                "20",
                "--no-pager",
            ],
            capture_output=True,
            text=True,
        )

        for line in reversed(
            result.stdout.splitlines()
        ):

            if "Configuration error:" in line:

                return line.split(
                    "Configuration error:",
                    1,
                )[1].strip()

        return None

    def start_with_error(
        self,
    ) -> tuple[bool, str | None]:

        self.start()

        if self.running:
            return True, None

        return False, self.last_error()

    def stop(self) -> bool:

        subprocess.run(
            [
                "sudo",
                "systemctl",
                "stop",
                self.SERVICE,
            ],
            check=True,
        )

        return not self.running

    def restart(self) -> bool:

        subprocess.run(
            [
                "sudo",
                "systemctl",
                "restart",
                self.SERVICE,
            ],
            check=True,
        )

        return self.running

    def status(self) -> StreamStatus:

        return StreamStatus(
            running=self.running,
            pid=self.pid,
        )
