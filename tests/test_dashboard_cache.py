import threading

from open_bos_stream.dashboard.service import DashboardService


def test_dashboard_status_bundles_rapid_parallel_polls() -> None:
    service = object.__new__(DashboardService)
    service._status_lock = threading.RLock()
    service._cached_status = None
    service._cached_status_at = 0.0
    builds = 0

    def build_status():
        nonlocal builds
        builds += 1
        return {"build": builds}

    service._build_status = build_status

    assert service.status() == {"build": 1}
    assert service.status() == {"build": 1}
    assert builds == 1


def test_dashboard_status_cache_expires_after_1_5_seconds(
    monkeypatch,
) -> None:
    service = object.__new__(DashboardService)
    service._status_lock = threading.RLock()
    service._cached_status = None
    service._cached_status_at = 0.0
    builds = 0
    now = [10.0]

    def build_status():
        nonlocal builds
        builds += 1
        return {"build": builds}

    monkeypatch.setattr(
        "open_bos_stream.dashboard.service.time.monotonic",
        lambda: now[0],
    )
    service._build_status = build_status

    assert service.status() == {"build": 1}
    now[0] = 11.4
    assert service.status() == {"build": 1}
    now[0] = 11.6
    assert service.status() == {"build": 2}
