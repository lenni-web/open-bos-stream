"""Zentrale Ausführung kurzlebiger Systemprozesse."""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from typing import Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class ProcessExecutionError(RuntimeError):
    def __init__(self, result: ProcessResult) -> None:
        self.result = result
        detail = result.stderr.strip() or result.stdout.strip()
        super().__init__(
            f"Prozess fehlgeschlagen ({result.returncode}): "
            f"{detail or result.command[0]}"
        )


class ProcessRunner:
    """Führt Befehle mit Timeout, Laufzeitmessung und Logging aus."""

    @staticmethod
    def _safe_command(command: tuple[str, ...]) -> str:
        safe: list[str] = []
        hide_next = False
        secret_flags = {
            "--password",
            "--token",
            "--stream-key",
        }

        for part in command:
            if hide_next:
                safe.append("***")
                hide_next = False
                continue
            if part in secret_flags:
                safe.append(part)
                hide_next = True
                continue
            if "://" in part:
                parsed = urlsplit(part)
                host = parsed.hostname or ""
                if parsed.port:
                    host = f"{host}:{parsed.port}"
                path = parsed.path
                if path and path != "/":
                    prefix, _, _ = path.rstrip("/").rpartition("/")
                    path = f"{prefix}/***" if prefix else "/***"
                safe.append(
                    urlunsplit(
                        (
                            parsed.scheme,
                            host,
                            path,
                            "",
                            "",
                        )
                    )
                )
                continue
            safe.append(part)

        return " ".join(safe)

    def run(
        self,
        command: Sequence[str],
        *,
        timeout: float = 10,
        check: bool = False,
        env: Mapping[str, str] | None = None,
    ) -> ProcessResult:
        args = tuple(str(part) for part in command)
        started = time.monotonic()
        logger.debug(
            "Starte Prozess: %s",
            self._safe_command(args),
        )

        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - started
            logger.warning(
                "Prozess-Timeout nach %.2fs: %s",
                duration,
                args[0],
            )
            raise TimeoutError(
                f"Zeitüberschreitung bei '{args[0]}' "
                f"nach {timeout:.1f} Sekunden."
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"Prozess '{args[0]}' konnte nicht gestartet werden: {exc}"
            ) from exc

        result = ProcessResult(
            command=args,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration=time.monotonic() - started,
        )
        logger.log(
            (
                logging.DEBUG
                if result.ok or not check
                else logging.WARNING
            ),
            "Prozess beendet: command=%s code=%s duration=%.2fs",
            args[0],
            result.returncode,
            result.duration,
        )

        if check and not result.ok:
            raise ProcessExecutionError(result)

        return result
