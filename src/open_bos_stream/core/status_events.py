"""Zustandswechsel aus dem Dashboard-Status als Protokollereignisse.

Läuft serverseitig alle paar Sekunden, unabhängig von geöffneten Browsern.
Ein Signalverlust wird erst nach zwei aufeinanderfolgenden Prüfungen
gemeldet, damit kurze Aussetzer das Protokoll nicht fluten.
"""

from __future__ import annotations

from dataclasses import dataclass, field

LOSS_CONFIRMATIONS = 2


@dataclass
class StatusEventTracker:
    _initialized: bool = False
    _sources: dict[str, dict] = field(default_factory=dict)
    _mediamtx: bool | None = None
    _storage: str | None = None
    _outputs_failed: dict[str, bool] = field(default_factory=dict)
    _stream_running: bool | None = None
    _load: str | None = None

    def evaluate(self, status: dict) -> list[tuple[str, str]]:
        return [
            (level, message)
            for level, message, _ in self.evaluate_detailed(status)
        ]

    def evaluate_detailed(
        self,
        status: dict,
    ) -> list[tuple[str, str, int | None]]:
        """Wie evaluate, dazu die Organisation (nur bei Quellenereignissen)."""

        events: list[tuple[str, str, int | None]] = []
        sources = status.get("sources") or []
        if not self._initialized:
            self._initialized = True
            online = sum(1 for item in sources if item.get("ready"))
            events.append((
                "success" if online else "info",
                f"📡 {online} von {len(sources)} Quellen online",
                None,
            ))
        events += self._check_sources(sources)
        for check in (
            self._check_mediamtx,
            self._check_storage,
            self._check_outputs,
            self._check_stream,
            self._check_load,
        ):
            events += [(level, message, None) for level, message in check(status)]
        return events

    def _check_sources(
        self,
        sources: list[dict],
    ) -> list[tuple[str, str, int | None]]:
        events = []
        current = set()
        for source in sources:
            source_id = str(source.get("id"))
            current.add(source_id)
            name = source.get("name") or source_id
            organization_id = source.get("organization_id")
            ready = bool(source.get("ready"))
            state = self._sources.get(source_id)
            if state is None:
                self._sources[source_id] = {"ready": ready, "misses": 0}
                continue
            if ready:
                if not state["ready"]:
                    events.append((
                        "success",
                        f"🟢 {name}: Signal verfügbar",
                        organization_id,
                    ))
                state.update(ready=True, misses=0)
                continue
            if state["ready"]:
                state["misses"] += 1
                if state["misses"] >= LOSS_CONFIRMATIONS:
                    events.append((
                        "warning",
                        f"🔴 {name}: Signal verloren",
                        organization_id,
                    ))
                    state.update(ready=False, misses=0)
        for source_id in set(self._sources) - current:
            del self._sources[source_id]
        return events

    def _check_mediamtx(self, status: dict) -> list[tuple[str, str]]:
        online = bool(
            ((status.get("services") or {}).get("mediamtx") or {}).get("online")
        )
        previous, self._mediamtx = self._mediamtx, online
        if previous is None or previous == online:
            return []
        return [
            ("success", "📡 Streaming-Server wieder erreichbar")
            if online
            else ("error", "📡 Streaming-Server nicht erreichbar")
        ]

    def _check_load(self, status: dict) -> list[tuple[str, str]]:
        load = status.get("server_load") or {}
        level = load.get("level")
        if level is None:
            return []
        previous, self._load = self._load, level
        if previous is None or previous == level:
            return []
        reasons = ", ".join(load.get("reasons") or [])
        detail = f" ({reasons})" if reasons else ""
        sources = load.get("active_sources")
        count = f" bei {sources} aktiven Quellen" if sources else ""
        if level == "critical":
            return [("error", f"🖥 Server überlastet{detail}{count}")]
        if level == "warning":
            return [("warning", f"🖥 Hohe Serverauslastung{detail}{count}")]
        return [("success", "🖥 Serverauslastung wieder normal")]

    def _check_storage(self, status: dict) -> list[tuple[str, str]]:
        storage = status.get("media_storage") or {}
        level = storage.get("level")
        if level is None:
            return []
        previous, self._storage = self._storage, level
        if previous is None or previous == level:
            return []
        free = storage.get("free_percent")
        free_text = (
            f"{float(free):.1f} % frei".replace(".", ",")
            if isinstance(free, (int, float))
            else ""
        )
        if level == "critical":
            return [("error", f"💾 Speicher erschöpft ({free_text}), neue Medien gesperrt")]
        if level == "warning":
            return [("warning", f"💾 Speicher wird knapp ({free_text})")]
        return [("success", f"💾 Wieder genug Speicher frei ({free_text})")]

    def _check_outputs(self, status: dict) -> list[tuple[str, str]]:
        events = []
        current = set()
        for output in status.get("stream_outputs") or []:
            name = str(output.get("name"))
            current.add(name)
            failed = bool(output.get("failed"))
            previous = self._outputs_failed.get(name)
            self._outputs_failed[name] = failed
            if previous is False and failed:
                events.append((
                    "error",
                    f"📺 Weiterleitung „{name}“ unerwartet beendet",
                ))
        for name in set(self._outputs_failed) - current:
            del self._outputs_failed[name]
        return events

    def _check_stream(self, status: dict) -> list[tuple[str, str]]:
        stream = status.get("stream") or {}
        if not stream.get("controllable"):
            return []
        running = bool(stream.get("running"))
        previous, self._stream_running = self._stream_running, running
        if previous is None or previous == running:
            return []
        return [
            ("success", "🟢 Streamer gestartet")
            if running
            else ("warning", "🔴 Streamer gestoppt")
        ]
