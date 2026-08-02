"""
Recording Manager

Zentrale Steuerung der Videoaufzeichnung.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from open_bos_stream.recording.command import RecordingCommandBuilder
from open_bos_stream.recording.process import RecordingProcess
class RecordingManager:

    def __init__(self) -> None:

        self._builder = RecordingCommandBuilder()

        self._process = RecordingProcess()

        self._final_file: Path | None = None

        self._working_file: Path | None = None

    @property
    def running(self) -> bool:

        return self._process.running

    @property
    def pid(self) -> int | None:

        return self._process.pid

    def start(
        self,
        filename: Path,
        input_url: str,
        *,
        transcode_video: bool = False,
        transcode_audio: bool = False,
    ) -> bool:

        if self.running:
            return True

        working_file = filename.with_name(f".{filename.name}.part")
        working_file.unlink(missing_ok=True)
        command = self._builder.build(
            working_file,
            input_url,
            transcode_video=transcode_video,
            transcode_audio=transcode_audio,
        )

        try:
            self._process.start(command)
        except Exception:
            working_file.unlink(missing_ok=True)
            raise

        self._final_file = filename
        self._working_file = working_file

        return self.running

    def stop(self) -> bool:
        if self._working_file is None or self._final_file is None:
            return True

        returncode = self._process.stop()
        working_file = self._working_file
        final_file = self._final_file
        self._working_file = None
        self._final_file = None

        if returncode != 0:
            working_file.unlink(missing_ok=True)
            raise RuntimeError(
                "Aufnahme wurde von FFmpeg nicht sauber abgeschlossen: "
                f"{self._process.last_error or f'Exit {returncode}'}"
            )
        self._validate(working_file)
        working_file.replace(final_file)
        return True

    @staticmethod
    def _validate(file: Path) -> None:
        if not file.exists() or file.stat().st_size == 0:
            file.unlink(missing_ok=True)
            raise RuntimeError("Aufnahme enthält keine Videodaten.")
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=codec_type",
                    "-of", "csv=p=0",
                    str(file),
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            file.unlink(missing_ok=True)
            raise RuntimeError(
                f"Aufnahme konnte nicht validiert werden: {exc}"
            ) from exc
        if result.returncode != 0 or "video" not in result.stdout.lower():
            detail = result.stderr.strip()
            file.unlink(missing_ok=True)
            raise RuntimeError(
                "Aufnahme ist keine gültige MP4-Videodatei"
                + (f": {detail}" if detail else ".")
            )
