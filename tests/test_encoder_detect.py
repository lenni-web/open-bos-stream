from open_bos_stream.stream.encoder.detect import EncoderDetector


class MissingRunner:
    def run(self, *args, **kwargs):
        raise RuntimeError("ffmpeg fehlt")


def test_encoder_detection_keeps_copy_when_ffmpeg_is_missing() -> None:
    assert EncoderDetector(MissingRunner()).available() == {"copy"}
