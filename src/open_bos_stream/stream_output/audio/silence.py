from .base import BaseAudio
from .command import AudioCommand


class SilenceAudio(BaseAudio):

    def build(self) -> AudioCommand:

        return AudioCommand(

            inputs=[
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
            ],

            mapping=[
                "-map",
                "0:v:0",

                "-map",
                "1:a:0",
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

                "-shortest",
            ],
        )