from dataclasses import dataclass, field


@dataclass(slots=True)
class AudioCommand:
    inputs: list[str] = field(default_factory=list)
    options: list[str] = field(default_factory=list)