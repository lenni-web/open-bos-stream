from open_bos_stream.core.config import ConfigLoader


def test_config_save_and_last_known_good_are_separate(tmp_path) -> None:
    source = ConfigLoader().load()
    loader = ConfigLoader(str(tmp_path / "stream.yaml"))

    loader.save(source)
    changed = source.model_copy(deep=True)
    changed.encoder.bitrate = "4M"
    loader.save_last_known_good(changed)

    assert loader.load().encoder.bitrate != "4M"
    assert loader.load_last_known_good().encoder.bitrate == "4M"
    assert not list(tmp_path.glob("*.tmp"))
