"""
Recorder

Verwaltet Videoaufzeichnungen.
"""

from pathlib import Path
from datetime import datetime


class Recorder:

    def __init__(self, directory: str = "recordings"):

        self.directory = Path(directory)
        self.directory.mkdir(exist_ok=True)

    def next_filename(self) -> Path:

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        return self.directory / f"recording_{timestamp}.mp4"
