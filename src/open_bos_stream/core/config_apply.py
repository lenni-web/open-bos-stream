"""Atomisches Anwenden der Stream-Konfiguration."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.core.config_preflight import (
    ConfigPreflightError,
    ConfigPreflightValidator,
)
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
        preflight: ConfigPreflightValidator | None = None,
        probe: Reloadable | None = None,
    ) -> None:
        self._loader = loader
        self._runtime = runtime_config
        self._stream = stream
        self._outputs = outputs
        self._preflight = preflight or ConfigPreflightValidator()
        self._probe = probe

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
            config.source_profile in {
                "rtmp_passthrough",
                "rtmp_repair",
            }
            and not config.input.url
        ):
            raise ConfigApplyError(
                "Für das RTMP-Profil fehlt die Eingangs-URL."
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
        if self._probe is not None:
            self._probe.reload(self._runtime)

    def apply(self, candidate: AppConfig) -> str:
        checks = self.test(candidate)

        previous = self._runtime.model_copy(deep=True)
        previous_managed = self._stream.managed

        try:
            if previous_managed and candidate.passthrough_active:
                self._stream.stop()

            self._loader.save(candidate)
            self._replace_runtime(candidate)

            if candidate.passthrough_active:
                if self._stream.running:
                    self._loader.save_last_known_good(candidate)
                return (
                    f"Vorabprüfung erfolgreich ({len(checks)} Prüfungen). "
                    "RTMP-Passthrough aktiv; warte auf Publisher an "
                    f"'{candidate.stream.name}'."
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

            self._loader.save_last_known_good(candidate)
            return (
                f"Vorabprüfung erfolgreich ({len(checks)} Prüfungen). "
                f"Profil '{candidate.source_profile}' aktiviert und "
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

    def test(self, candidate: AppConfig) -> list[str]:
        """Prüft eine Konfiguration ohne sie zu speichern."""

        self._validate(candidate)
        try:
            return self._preflight.validate(candidate)
        except ConfigPreflightError as exc:
            raise ConfigApplyError(
                f"Vorabprüfung fehlgeschlagen: {exc}"
            ) from exc

    def restore_last_known_good(self) -> str:
        try:
            candidate = self._loader.load_last_known_good()
        except FileNotFoundError as exc:
            raise ConfigApplyError(
                "Es ist noch keine funktionierende "
                "Konfiguration gesichert."
            ) from exc

        return self.apply(candidate)
