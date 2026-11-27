from __future__ import annotations

from open_bos_stream.api.dashboard import filter_status_sources
from open_bos_stream.core.status_events import StatusEventTracker
from open_bos_stream.notifications.monitor import NotificationMonitor
from open_bos_stream.system.load import ServerLoadMonitor


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def monitor(load: float | None = 0.3):
    clock = Clock()
    return ServerLoadMonitor(clock=clock, load_reader=lambda: (load, 4)), clock


def feed(load_monitor, clock, cpu: float, ram: float = 40, seconds: int = 30) -> None:
    for _ in range(seconds // 2):
        clock.now += 2
        load_monitor.sample(cpu, ram)


def test_short_spike_does_not_warn() -> None:
    load_monitor, clock = monitor()
    feed(load_monitor, clock, 30, seconds=26)
    feed(load_monitor, clock, 100, seconds=4)
    assert load_monitor.status(active_sources=9)["level"] == "ok"


def test_sustained_high_cpu_warns_and_recovers_with_hysteresis() -> None:
    load_monitor, clock = monitor()
    feed(load_monitor, clock, 88)
    status = load_monitor.status(active_sources=10)
    assert status["level"] == "warning"
    assert "CPU 88 %" in status["reasons"]
    assert "10 aktiven Quellen" in status["message"]

    # Knapp unter der Schwelle bleibt der Hinweis (kein Flackern).
    feed(load_monitor, clock, 76)
    assert load_monitor.status()["level"] == "warning"
    feed(load_monitor, clock, 50)
    assert load_monitor.status()["level"] == "ok"


def test_critical_by_memory_or_system_load() -> None:
    load_monitor, clock = monitor()
    feed(load_monitor, clock, 40, ram=95)
    assert load_monitor.status()["level"] == "critical"

    busy, clock = monitor(load=1.7)
    feed(busy, clock, 40)
    status = busy.status()
    assert status["level"] == "critical" and "Systemlast 1,7 je Kern" in status["reasons"]


def test_overload_is_reported_after_two_minutes_and_logged() -> None:
    status = {"server_load": {"level": "critical", "reasons": ["CPU 97 %"], "active_sources": 12}}
    notifier = NotificationMonitor()
    notifier.evaluate({}, 0)
    assert not [n for n in notifier.evaluate(status, 10) if n.event == "server_load"]
    notices = [n for n in notifier.evaluate(status, 140) if n.event == "server_load"]
    assert notices and "12 aktiven Quellen" in notices[0].body
    recovered = notifier.evaluate({"server_load": {"level": "ok"}}, 200)
    assert any(n.event == "server_load" and n.recovery for n in recovered)

    tracker = StatusEventTracker()
    tracker.evaluate({"server_load": {"level": "ok"}})
    assert tracker.evaluate(status) == [("error", "🖥 Server überlastet (CPU 97 %) bei 12 aktiven Quellen")]


def test_restricted_users_do_not_learn_total_source_count() -> None:
    data = {"sources": [], "server_load": {
        "level": "warning", "reasons": ["CPU 85 %"], "active_sources": 14,
        "message": "Hohe Serverauslastung (CPU 85 %) bei 14 aktiven Quellen.",
    }}
    filtered = filter_status_sources(data, set())["server_load"]
    assert filtered["active_sources"] is None
    assert "14" not in filtered["message"] and "CPU 85 %" in filtered["message"]
