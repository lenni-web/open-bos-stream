from abc import ABC, abstractmethod

from open_bos_stream.core.models import (
    AppConfig,
    StreamOutputConfig,
)

class BaseOutput(ABC):

    def validate(
        self,
        output: StreamOutputConfig,
    ) -> None:
        return

    @abstractmethod
    def build(
        self,
        config: AppConfig,
        output: StreamOutputConfig,
    ) -> list[str]:
        ...