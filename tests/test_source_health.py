from open_bos_stream.stream.source_health import source_health


def health(runtime=None, *, ready=True, online=True, managed=True):
    return source_health(
        ready=ready,
        online=online,
        managed=managed,
        runtime=runtime,
        now=1_000.0,
    )["code"]


def test_direct_source_is_stable_or_offline_without_ffmpeg_metrics() -> None:
    assert health(None, managed=False) == "stable"
    assert health(None, ready=False, online=False, managed=False) == "offline"


def test_restart_loop_has_priority_over_other_runtime_warnings() -> None:
    assert health({
        "state": "waiting_restart",
        "restart_count": 3,
        "last_restart_at": 950,
    }) == "restart_loop"


def test_waiting_for_rtmp_publisher_is_not_a_restart_loop() -> None:
    assert health({
        "state": "waiting_source",
        "restart_count": 20,
        "last_restart_at": 990,
    }, ready=False, online=False) == "offline"


def test_stalled_and_slow_sources_are_distinguished() -> None:
    assert health({
        "state": "restarting",
        "last_restart_reason": "stale",
    }) == "stalled"
    assert health({
        "state": "running",
        "speed": 0.78,
    }) == "under_load"


def test_recent_drop_or_dup_marks_timing_issue() -> None:
    assert health({
        "state": "running",
        "speed": 1.0,
        "last_drop_at": 990,
    }) == "timing_issue"
    assert health({
        "state": "running",
        "speed": 1.0,
        "last_drop_at": 900,
    }) == "stable"
