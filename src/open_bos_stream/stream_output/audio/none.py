from .base import BaseAudio
from .command import AudioCommand


class NoneAudio(BaseAudio):

    def build(self) -> AudioCommand:

        return AudioCommand()