from open_bos_stream.stream.progress import FFmpegProgress


def _feed_block(progress: FFmpegProgress, frame: int, out_time: int, now: float) -> bool:
    progress.feed(f"frame={frame}", now=now)
    progress.feed(f"out_time_us={out_time}", now=now)
    progress.feed("fps=29.97", now=now)
    progress.feed("speed=1.01x", now=now)
    return progress.feed("progress=continue", now=now)


def test_progress_only_advances_when_media_timestamps_or_frames_change() -> None:
    progress = FFmpegProgress()

    assert _feed_block(progress, 12, 400_000, 10.0) is True
    assert progress.last_advance == 10.0
    assert progress.fps == 29.97
    assert progress.speed == 1.01

    assert _feed_block(progress, 12, 400_000, 12.0) is False
    assert progress.last_advance == 10.0


def test_stale_detection_has_separate_startup_grace() -> None:
    progress = FFmpegProgress()

    assert progress.stale(
        now=19.0,
        started_at=0.0,
        startup_grace=20.0,
        timeout=12.0,
    ) is False
    assert progress.stale(
        now=21.0,
        started_at=0.0,
        startup_grace=20.0,
        timeout=12.0,
    ) is True

    _feed_block(progress, 1, 33_000, 25.0)
    assert progress.stale(
        now=36.0,
        started_at=0.0,
        startup_grace=20.0,
        timeout=12.0,
    ) is False
    assert progress.stale(
        now=38.0,
        started_at=0.0,
        startup_grace=20.0,
        timeout=12.0,
    ) is True
