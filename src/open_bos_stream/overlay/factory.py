from open_bos_stream.core.models import OverlayConfig
from open_bos_stream.stream.exceptions import ConfigurationError

from .base import BaseOverlay
from .clock import ClockOverlay
from .none import NoneOverlay
from .renderer import RendererOverlay


class OverlayFactory:
    @staticmethod
    def create(config: OverlayConfig) -> BaseOverlay:
        if config.source == "none":
            return NoneOverlay(config)

        if config.source == "clock":
            return ClockOverlay(config)

        if config.source == "renderer":
            return RendererOverlay(config)

        raise ConfigurationError(
            f"Unknown overlay source '{config.source}'."
        )