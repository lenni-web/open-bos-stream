from dataclasses import dataclass, field


@dataclass(slots=True)
class OverlayCommand:
    inputs: list[str] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)

    overlay_filter: str = "overlay=x=0:y=0"