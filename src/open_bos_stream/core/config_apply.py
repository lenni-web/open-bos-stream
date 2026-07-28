"""Atomisches Anwenden der Stream-Konfiguration."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.models import AppConfig


class Reloadable(Protocol):
    def reload(self, config: AppConfig) -> None: ...


class StreamController(Reloadable, Protocol):
    @property
    def managed(self) -> bool: ...

    def start(self) -> bool: ...
    def stop(self) -> bool: ...
    def restart(self) -> bool: ...
    def wait_until_ready(self, timeout: float = 8.0) -> bool: ...


class ConfigApplyError(RuntimeError):
    """Die neue Konfiguration konnte nicht aktiviert werden."""


class ConfigApplyService:
    """Persistiert und aktiviert eine Konfiguration mit Rollback."""

    def __init__(
        self,
        loader: ConfigLoader,
        runtime_config: AppConfig,
        stream: StreamController,
        outputs: Reloadable,
    ) -> None:
        self._loader = loader
        self._runtime = runtime_config
        self._stream = stream
        self._outputs = outputs

    @staticmethod
    def _validate(config: AppConfig) -> None:
        if (
            config.source_profile == "capture_card"
            and not Path(config.input.device or "").exists()
        ):
            raise ConfigApplyError(
                "Capture-Gerät "
                f"'{config.input.device}' ist nicht verfügbar."
            )

        if (
            config.source_profile == "rtmp_passthrough"
            and not config.input.url
        ):
            raise ConfigApplyError(
                "Für RTMP-Passthrough fehlt die Eingangs-URL."
            )

    def _replace_runtime(self, config: AppConfig) -> None:
        for field_name in AppConfig.model_fields:
            setattr(
                self._runtime,
                field_name,
                getattr(config, field_name),
            )

        self._stream.reload(self._runtime)
        self._outputs.reload(self._runtime)

    def apply(self, candidate: AppConfig) -> str:
        self._validate(candidate)

        previous = self._runtime.model_copy(deep=True)
        previous_managed = self._stream.managed

        try:
            if previous_managed and candidate.passthrough_active:
                self._stream.stop()

            self._loader.save(candidate)
            self._replace_runtime(candidate)

            if candidate.passthrough_active:
                return (
                    "RTMP-Passthrough aktiv; warte auf "
                    f"Publisher an '{candidate.stream.name}'."
                )

            if not self._stream.restart():
                raise ConfigApplyError(
                    "Der Streamer wurde nicht aktiv."
                )

            if not self._stream.wait_until_ready():
                raise ConfigApplyError(
                    "MediaMTX hat den neuen Stream nicht "
                    "innerhalb des Zeitlimits erkannt."
                )

            return (
                "Capture-Card-Profil aktiviert und "
                "Streamer neu gestartet."
            )

        except Exception as exc:
            try:
                if self._stream.managed:
                    self._stream.stop()
            except Exception:
                pass

            self._loader.save(previous)
            self._replace_runtime(previous)

            if previous_managed:
                try:
                    self._stream.restart()
                except Exception:
                    pass

            if isinstance(exc, ConfigApplyError):
                raise

            raise ConfigApplyError(str(exc)) from exc
