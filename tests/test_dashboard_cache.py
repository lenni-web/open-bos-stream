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
