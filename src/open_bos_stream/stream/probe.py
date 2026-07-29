"""Passive Diagnose einer laufenden Streamquelle mit ffprobe."""

from __future__ import annotations

import json
import threading
import time
from fractions import Fraction

from open_bos_stream.core.models import AppConfig
from open_bos_stream.core.process import ProcessRunner


class StreamProbeService:
    CACHE_SECONDS = 15.0

    def __init__(
        self,
        config: AppConfig,
        runner: ProcessRunner | None = None,
        background: bool = True,
    ) -> None:
        self._config = config
        self._runner = runner or ProcessRunner()
        self._background = background
        self._cached: dict | None = None
        self._cached_at = 0.0
        self._probing = False
        self._lock = threading.Lock()
        self._generation = 0

    def reload(self, config: AppConfig) -> None:
        self._config = config
        self._cached = None
        self._cached_at = 0.0
        self._generation += 1

    def _refresh(self, generation: int) -> None:
        result = self._probe()
        with self._lock:
            if generation == self._generation:
                self._cached = result
                self._cached_at = time.monotonic()
            self._probing = False

    @staticmethod
    def _rate(value: str | None) -> float:
        if not value or value == "0/0":
            return 0.0
        try:
            return float(Fraction(value))
        except (ValueError, ZeroDivisionError):
            return 0.0

    def _target(self) -> str:
        if self._config.passthrough_active:
            return self._config.input.url or ""
        return self._config.stream.rtsp_url

    def _probe(self) -> dict:
        target = self._target()
        if not target:
            return {
                "available": False,
                "error": "Keine diagnostizierbare Quelle konfiguriert.",
                "warnings": [],
            }

        command = [
            "ffprobe",
            "-v",
            "error",
        ]
        if target.startswith("rtsp://"):
            command.extend(["-rtsp_transport", "tcp"])
        command.extend([
            "-read_intervals",
            "%+3",
            "-show_streams",
            "-show_packets",
            "-select_streams",
            "v:0",
            "-show_entries",
            (
                "stream=codec_name,codec_type,width,height,"
                "r_frame_rate,avg_frame_rate,time_base,has_b_frames:"
                "packet=pts_time,dts_time"
            ),
            "-of",
            "json",
            target,
        ])

        try:
            result = self._runner.run(command, timeout=8)
        except (RuntimeError, TimeoutError) as exc:
            return {
                "available": False,
                "error": str(exc),
                "warnings": [],
            }

        if not result.ok:
            return {
                "available": False,
                "error": (
                    result.stderr.strip()
                    or "ffprobe konnte die Quelle nicht lesen."
                ),
                "warnings": [],
            }

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {
                "available": False,
                "error": "ffprobe lieferte ungültige Diagnosedaten.",
                "warnings": [],
            }

        stream = next(iter(payload.get("streams", [])), {})
        packets = payload.get("packets", [])
        nominal_fps = self._rate(stream.get("r_frame_rate"))
        average_fps = self._rate(stream.get("avg_frame_rate"))
        warnings: list[dict[str, str]] = []

        if nominal_fps > 240:
            warnings.append({
                "code": "implausible_frame_rate",
                "message": (
                    f"Unplausible nominelle Bildrate "
                    f"({nominal_fps:g} fps)."
                ),
            })

        previous_dts: float | None = None
        backwards = 0
        missing = 0
        for packet in packets:
            raw_dts = packet.get("dts_time")
            if raw_dts in (None, "N/A"):
                missing += 1
                continue
            try:
                dts = float(raw_dts)
            except (TypeError, ValueError):
                missing += 1
                continue
            if previous_dts is not None and dts < previous_dts:
                backwards += 1
            previous_dts = dts

        if backwards:
            warnings.append({
                "code": "non_monotonic_dts",
                "message": (
                    f"{backwards} rückwärtslaufende DTS-Zeitstempel "
                    "im Messfenster erkannt."
                ),
            })
        if packets and missing == len(packets):
            warnings.append({
                "code": "missing_dts",
                "message": "Die Quelle liefert keine auswertbaren DTS.",
            })

        return {
            "available": True,
            "target": target,
            "codec": stream.get("codec_name"),
            "width": stream.get("width", 0),
            "height": stream.get("height", 0),
            "nominal_fps": nominal_fps,
            "average_fps": average_fps,
            "time_base": stream.get("time_base"),
            "has_b_frames": stream.get("has_b_frames", 0),
            "packets_checked": len(packets),
            "backwards_dts": backwards,
            "warnings": warnings,
            "error": None,
        }

    def status(self, source_ready: bool) -> dict:
        now = time.monotonic()
        if not source_ready:
            return {
                "available": False,
                "error": "Quelle ist noch nicht online.",
                "warnings": [],
            }
        if (
            self._cached is not None
            and now - self._cached_at < self.CACHE_SECONDS
        ):
            return self._cached

        if not self._background:
            self._refresh(self._generation)
            assert self._cached is not None
            return self._cached

        with self._lock:
            if not self._probing:
                self._probing = True
                threading.Thread(
                    target=self._refresh,
                    args=(self._generation,),
                    name="open-bos-stream-probe",
                    daemon=True,
                ).start()

        return self._cached or {
            "available": False,
            "pending": True,
            "error": "Messung läuft.",
            "warnings": [],
        }
