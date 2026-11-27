"""Serverauslastung beobachten und bewerten.

Die Zahl gleichzeitiger Quellen ist nicht mehr fest begrenzt. Stattdessen
bewertet dieser Dienst laufend CPU, Arbeitsspeicher und Systemlast. Kurze
Spitzen (z. B. beim Start einer Quelle) lösen keinen Hinweis aus: Bewertet
wird der Mittelwert der letzten 30 Sekunden, und eine Stufe gilt erst als
beendet, wenn die Werte deutlich darunter liegen (Hysterese).
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass

WINDOW_SECONDS = 30
MIN_SAMPLE_GAP = 1.0
# Wie stark die Werte unter die Schwelle fallen müssen, bevor eine Stufe endet.
HYSTERESIS = 8.0


@dataclass(frozen=True)
class LoadThresholds:
    cpu_warning: float = 80.0
    cpu_critical: float = 93.0
    ram_warning: float = 85.0
    ram_critical: float = 93.0
    # Systemlast (1 min) je CPU-Kern.
    load_warning: float = 1.0
    load_critical: float = 1.5


LEVELS = ("ok", "warning", "critical")


def _load_per_core() -> tuple[float | None, int]:
    cores = os.cpu_count() or 1
    try:
        return os.getloadavg()[0] / cores, cores
    except (AttributeError, OSError):
        return None, cores


class ServerLoadMonitor:
    def __init__(
        self,
        thresholds: LoadThresholds | None = None,
        *,
        clock=time.monotonic,
        load_reader=_load_per_core,
    ) -> None:
        self.thresholds = thresholds or LoadThresholds()
        self._clock = clock
        self._load_reader = load_reader
        self._samples: deque[tuple[float, float, float, float | None]] = deque()
        self._level = "ok"
        self._since: float | None = None
        self._cores = os.cpu_count() or 1
        self._lock = threading.Lock()

    def sample(self, cpu: float | None, ram: float | None) -> None:
        """Messwert aus der Statusabfrage übernehmen."""

        if cpu is None or ram is None:
            return
        now = self._clock()
        load, self._cores = self._load_reader()
        with self._lock:
            if self._samples and now - self._samples[-1][0] < MIN_SAMPLE_GAP:
                return
            self._samples.append((now, float(cpu), float(ram), load))
            while self._samples and now - self._samples[0][0] > WINDOW_SECONDS:
                self._samples.popleft()

    def _averages(self) -> tuple[float, float, float | None]:
        cpu = sum(item[1] for item in self._samples) / len(self._samples)
        ram = self._samples[-1][2]
        loads = [item[3] for item in self._samples if item[3] is not None]
        load = sum(loads) / len(loads) if loads else None
        return cpu, ram, load

    def _measured_level(self, cpu: float, ram: float, load: float | None, margin: float = 0.0) -> str:
        limits = self.thresholds
        load_margin = margin / 100
        if (
            cpu >= limits.cpu_critical - margin
            or ram >= limits.ram_critical - margin
            or (load is not None and load >= limits.load_critical - load_margin)
        ):
            return "critical"
        if (
            cpu >= limits.cpu_warning - margin
            or ram >= limits.ram_warning - margin
            or (load is not None and load >= limits.load_warning - load_margin)
        ):
            return "warning"
        return "ok"

    def status(self, active_sources: int = 0) -> dict:
        with self._lock:
            if not self._samples:
                return {"level": "ok", "samples": 0, "active_sources": active_sources}
            cpu, ram, load = self._averages()
            measured = self._measured_level(cpu, ram, load)
            current = LEVELS.index(self._level)
            if LEVELS.index(measured) > current:
                self._level = measured
                self._since = self._clock()
            elif LEVELS.index(measured) < current:
                # Erst zurückstufen, wenn die Werte deutlich darunter liegen.
                relaxed = self._measured_level(cpu, ram, load, margin=HYSTERESIS)
                if LEVELS.index(relaxed) < current:
                    self._level = relaxed
                    self._since = self._clock() if relaxed != "ok" else None
            level = self._level
            since = self._since
            samples = len(self._samples)
        reasons = []
        limits = self.thresholds
        if cpu >= limits.cpu_warning - (HYSTERESIS if level != "ok" else 0):
            reasons.append(f"CPU {cpu:.0f} %")
        if ram >= limits.ram_warning - (HYSTERESIS if level != "ok" else 0):
            reasons.append(f"Arbeitsspeicher {ram:.0f} %")
        if load is not None and load >= limits.load_warning - (HYSTERESIS / 100 if level != "ok" else 0):
            reasons.append(f"Systemlast {load:.1f} je Kern".replace(".", ","))
        return {
            "level": level,
            "cpu": round(cpu, 1),
            "ram": round(ram, 1),
            "load_per_core": round(load, 2) if load is not None else None,
            "cores": self._cores,
            "active_sources": active_sources,
            "reasons": reasons,
            "for_seconds": int(self._clock() - since) if since is not None else 0,
            "samples": samples,
            "message": message(level, reasons, active_sources),
        }


def message(level: str, reasons: list[str], active_sources: int) -> str:
    if level == "ok":
        return ""
    detail = f" ({', '.join(reasons)})" if reasons else ""
    sources = f" bei {active_sources} aktiven Quellen" if active_sources else ""
    if level == "critical":
        return (
            f"Server sehr stark ausgelastet{detail}{sources}. Livebilder, Aufnahmen "
            "und Weiterleitungen können ruckeln oder abbrechen. Nicht benötigte "
            "Quellen deaktivieren oder das sparsame Vorschauprofil wählen."
        )
    return (
        f"Hohe Serverauslastung{detail}{sources}. Weitere Quellen, Aufnahmen "
        "oder Weiterleitungen können die Bildqualität beeinträchtigen."
    )
