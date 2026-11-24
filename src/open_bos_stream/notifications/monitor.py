"""Erkennt Störungen im Dashboard-Status und erzeugt Meldungen.

Reine Zustandslogik ohne Versand, damit sie sich mit festen Zeitpunkten
testen lässt. Kurze Aussetzer lösen keine Meldung aus (Wartezeit), und je
Störung wird höchstens alle zehn Minuten gemeldet (Sperrzeit). Nach einer
gemeldeten Störung folgt eine Entwarnung, sobald alles wieder läuft.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SOURCE_OFFLINE_DELAY_SECONDS = 30
MEDIAMTX_OFFLINE_DELAY_SECONDS = 20
ALERT_COOLDOWN_SECONDS = 600

RECORDING_PROBLEM_REASONS = {
    "stream_interrupted": "Aufnahme durch Streamabbruch beendet",
    "failed": "Aufnahme fehlgeschlagen",
    "storage_low": "Aufnahme wegen Speichermangel beendet",
}


STREAM_URL_PATTERN = re.compile(
    r"\b(rtmps?|srt|rtsps?|https?)://([^\s/'\"?]+)[^\s'\"]*",
    re.IGNORECASE,
)


def mask_stream_urls(text: str) -> str:
    """Ziel-URLs ohne Pfad und Stream-Schlüssel (wie in der Oberfläche)."""

    def replace(match: re.Match) -> str:
        host = match.group(2).rsplit("@", 1)[-1]
        return f"{match.group(1)}://{host}/***"

    return STREAM_URL_PATTERN.sub(replace, text)


@dataclass(frozen=True)
class Notice:
    """Eine zu versendende Meldung."""

    event: str
    subject: str
    body: str
    recovery: bool = False


@dataclass
class _Tracked:
    seen_online: bool = False
    problem_since: float | None = None
    alerted: bool = False


@dataclass
class NotificationMonitor:
    source_delay: float = SOURCE_OFFLINE_DELAY_SECONDS
    mediamtx_delay: float = MEDIAMTX_OFFLINE_DELAY_SECONDS
    cooldown: float = ALERT_COOLDOWN_SECONDS

    _initialized: bool = False
    _sources: dict[str, _Tracked] = field(default_factory=dict)
    _mediamtx: _Tracked = field(default_factory=_Tracked)
    _storage_level: str = "ok"
    _storage_alerted: bool = False
    _recording_finished_at: float | None = None
    _outputs: dict[str, _Tracked] = field(default_factory=dict)
    _last_alert: dict[str, float] = field(default_factory=dict)

    # ------------------------------------------------------------------

    def evaluate(self, status: dict, now: float) -> list[Notice]:
        notices: list[Notice] = []
        if not self._initialized:
            self._initialized = True
            notices.append(
                Notice(
                    event="server_started",
                    subject="Open BOS Stream wurde gestartet",
                    body=(
                        "Der Dienst wurde gestartet, z. B. nach einem Update, "
                        "einem Neustart des Servers oder einem Absturz."
                    ),
                )
            )
            # Bereits vor dem Start beendete Aufnahmen nicht melden.
            self._recording_finished_at = (
                status.get("recording") or {}
            ).get("finished_at")

        notices += self._check_mediamtx(status, now)
        notices += self._check_sources(status, now)
        notices += self._check_storage(status, now)
        notices += self._check_recording(status, now)
        notices += self._check_outputs(status, now)
        return notices

    # ------------------------------------------------------------------

    def _alert_allowed(self, key: str, now: float) -> bool:
        last = self._last_alert.get(key)
        if last is not None and now - last < self.cooldown:
            return False
        self._last_alert[key] = now
        return True

    def _delayed_problem(
        self,
        key: str,
        tracked: _Tracked,
        problem: bool,
        now: float,
        delay: float,
        alert: Notice,
        recovery: Notice,
    ) -> list[Notice]:
        if problem:
            if tracked.problem_since is None:
                tracked.problem_since = now
            if (
                not tracked.alerted
                and now - tracked.problem_since >= delay
                and self._alert_allowed(key, now)
            ):
                tracked.alerted = True
                return [alert]
            return []
        tracked.problem_since = None
        if tracked.alerted:
            tracked.alerted = False
            return [recovery]
        return []

    def _check_mediamtx(self, status: dict, now: float) -> list[Notice]:
        online = bool(
            ((status.get("services") or {}).get("mediamtx") or {}).get(
                "online"
            )
        )
        return self._delayed_problem(
            "mediamtx",
            self._mediamtx,
            not online,
            now,
            self.mediamtx_delay,
            Notice(
                event="mediamtx_offline",
                subject="Störung: Streaming-Server nicht erreichbar",
                body=(
                    "MediaMTX ist seit mindestens "
                    f"{int(self.mediamtx_delay)} Sekunden nicht erreichbar. "
                    "Livebilder, Aufnahmen und Weiterleitungen sind "
                    "unterbrochen."
                ),
            ),
            Notice(
                event="mediamtx_offline",
                subject="Entwarnung: Streaming-Server wieder erreichbar",
                body="MediaMTX ist wieder erreichbar.",
                recovery=True,
            ),
        )

    def _check_sources(self, status: dict, now: float) -> list[Notice]:
        notices: list[Notice] = []
        current = set()
        for source in status.get("sources") or []:
            source_id = str(source.get("id"))
            current.add(source_id)
            name = source.get("name") or source_id
            online = bool(source.get("online"))
            tracked = self._sources.setdefault(source_id, _Tracked())
            if online:
                tracked.seen_online = True
            # Eine Quelle, die seit dem Start nie gesendet hat (Drohne nicht
            # in der Luft), ist keine Störung.
            if not tracked.seen_online:
                continue
            notices += self._delayed_problem(
                f"source:{source_id}",
                tracked,
                not online,
                now,
                self.source_delay,
                Notice(
                    event="source_offline",
                    subject=f"Störung: Quelle „{name}“ ohne Signal",
                    body=(
                        f"Die Quelle „{name}“ sendet seit mindestens "
                        f"{int(self.source_delay)} Sekunden kein Signal mehr."
                    ),
                ),
                Notice(
                    event="source_offline",
                    subject=f"Entwarnung: Quelle „{name}“ wieder online",
                    body=f"Die Quelle „{name}“ sendet wieder.",
                    recovery=True,
                ),
            )
        for source_id in set(self._sources) - current:
            # Entfernte oder deaktivierte Quellen nicht weiter verfolgen.
            del self._sources[source_id]
        return notices

    def _check_storage(self, status: dict, now: float) -> list[Notice]:
        storage = status.get("media_storage") or {}
        level = storage.get("level") or "ok"
        previous = self._storage_level
        self._storage_level = level
        free = storage.get("free_percent")
        free_text = (
            f"{float(free):.1f} %".replace(".", ",")
            if isinstance(free, (int, float))
            else "unbekannt"
        )
        if level == "ok":
            if self._storage_alerted:
                self._storage_alerted = False
                return [
                    Notice(
                        event="storage_low",
                        subject="Entwarnung: wieder genug Speicher frei",
                        body=f"Freier Speicher: {free_text}.",
                        recovery=True,
                    )
                ]
            return []
        escalated = previous == "ok" or (
            previous == "warning" and level == "critical"
        )
        if not escalated or not self._alert_allowed(
            f"storage:{level}", now
        ):
            return []
        self._storage_alerted = True
        if level == "critical":
            body = storage.get("blocked_message") or (
                "Die Mindestgrenze ist unterschritten."
            )
            subject = "Störung: Speicher erschöpft"
        else:
            body = (
                "Die Warnschwelle des Speicherschutzes ist unterschritten. "
                "Bitte Aufnahmen sichern oder löschen."
            )
            subject = "Warnung: Speicher wird knapp"
        return [
            Notice(
                event="storage_low",
                subject=subject,
                body=f"{body}\nFreier Speicher: {free_text}.",
            )
        ]

    def _check_recording(self, status: dict, now: float) -> list[Notice]:
        recording = status.get("recording") or {}
        finished_at = recording.get("finished_at")
        reason = recording.get("end_reason")
        if not finished_at or finished_at == self._recording_finished_at:
            return []
        self._recording_finished_at = finished_at
        title = RECORDING_PROBLEM_REASONS.get(reason)
        if title is None:
            return []
        source = recording.get("source_name")
        details = [recording.get("end_message") or title]
        if source:
            details.append(f"Quelle: {source}")
        if recording.get("completed_filename"):
            details.append(f"Datei: {recording['completed_filename']}")
        return [
            Notice(
                event="recording_problem",
                subject=title,
                body="\n".join(details),
            )
        ]

    def _check_outputs(self, status: dict, now: float) -> list[Notice]:
        notices: list[Notice] = []
        current = set()
        for output in status.get("stream_outputs") or []:
            name = str(output.get("name"))
            current.add(name)
            running = bool(output.get("running"))
            failed = bool(output.get("failed"))
            error = output.get("error") or ""
            tracked = self._outputs.setdefault(name, _Tracked())
            if running:
                tracked.seen_online = True
                if tracked.alerted:
                    tracked.alerted = False
                    notices.append(
                        Notice(
                            event="output_failed",
                            subject=(
                                f"Entwarnung: Streaming-Ausgang „{name}“ "
                                "läuft wieder"
                            ),
                            body=f"Der Streaming-Ausgang „{name}“ läuft wieder.",
                            recovery=True,
                        )
                    )
                continue
            was_running = tracked.seen_online
            tracked.seen_online = False
            # Nur unerwartete Abbrüche melden, kein manuelles Stoppen.
            if (
                was_running
                and failed
                and self._alert_allowed(f"output:{name}", now)
            ):
                tracked.alerted = True
                notices.append(
                    Notice(
                        event="output_failed",
                        subject=f"Störung: Streaming-Ausgang „{name}“ beendet",
                        body=(
                            f"Der Streaming-Ausgang „{name}“ wurde unerwartet "
                            "beendet."
                            + (
                                "\n\nLetzte FFmpeg-Meldungen:\n"
                                + mask_stream_urls(error)
                                if error
                                else ""
                            )
                        ),
                    )
                )
        for name in set(self._outputs) - current:
            del self._outputs[name]
        return notices
