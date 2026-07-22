from dataclasses import dataclass, field


@dataclass(slots=True)
class AudioCommand:
    """FFmpeg command fragments for an audio source."""

    inputs: list[str] = field(default_factory=list)
    mapping: list[str] = field(default_factory=list)
    options: list[str] = field(default_factory=list)