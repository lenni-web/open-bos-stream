from open_bos_stream.media.storage import MediaStorageService


def test_media_storage_reports_counts_and_sizes(tmp_path) -> None:
    recordings = tmp_path / "recordings"
    snapshots = tmp_path / "snapshots"
    recordings.mkdir()
    snapshots.mkdir()
    (recordings / "one.mp4").write_bytes(b"video")
    (snapshots / "one.jpg").write_bytes(b"image")
    (snapshots / "two.jpg").write_bytes(b"other")

    status = MediaStorageService(
        str(recordings),
        str(snapshots),
    ).status()

    assert status["recordings"] == 1
    assert status["snapshots"] == 2
    assert status["media_bytes"] == 15
    assert status["free_bytes"] > 0
    assert 0 <= status["used_percent"] <= 100
