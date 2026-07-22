from .base import BaseAudio
from .command import AudioCommand


class InputAudio(BaseAudio):
    """
    Uses the audio stream embedded in the internal RTSP stream.
    The internal streamer is expected to provide both video and audio.
    """

    def build(self) -> AudioCommand:
        return AudioCommand(
            mapping=[
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
            ],
            options=[
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "48000",
                "-ac",
                "2",
            ],
        )