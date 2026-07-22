"""
Open BOS Stream Runner

Startet FFmpeg anhand der Projektkonfiguration.
"""

from __future__ import annotations

import subprocess
import sys

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.stream.command import FFmpegCommandBuilder
from open_bos_stream.stream.exceptions import (
    ConfigurationError,
)

def main() -> int:

    config = ConfigLoader().load()

    try:

        command = FFmpegCommandBuilder(
            config
        ).build()

    except ConfigurationError as exc:

        print(
            f"Configuration error: {exc}",
            file=sys.stderr,
            flush=True,
        )

        return 2

    print("========================================", flush=True)
    print("Open BOS Stream", flush=True)
    ...
    print(" ".join(command), flush=True)

    sys.stdout.flush()

    return subprocess.call(command)


if __name__ == "__main__":

    sys.exit(main())
