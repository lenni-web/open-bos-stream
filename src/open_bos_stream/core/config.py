from pathlib import Path
import os
import tempfile

import yaml

from open_bos_stream.core.models import AppConfig


class ConfigLoader:

    def __init__(
        self,
        config_file: str = "config/stream.yaml",
    ) -> None:

        self.config_file = Path(config_file)

    def load(self) -> AppConfig:

        with self.config_file.open(
            "r",
            encoding="utf-8",
        ) as file:

            data = yaml.safe_load(file)

        # ---------------------------------------------------------
        # Migration: capture -> input
        # ---------------------------------------------------------

        if "input" not in data:

            capture = data.get(
                "capture",
                {},
            )

            data["input"] = {

                "type": "v4l2",

                "mode": "transcode",

                "device": capture.get(
                    "device",
                    "/dev/video0",
                ),

                "url": None,

                "width": capture.get(
                    "width",
                    1280,
                ),

                "height": capture.get(
                    "height",
                    720,
                ),

                "fps": capture.get(
                    "fps",
                    25,
                ),

                "format": capture.get(
                    "format",
                    "v4l2",
                ),

            }

            data["input"].setdefault(
                "mode",
                "transcode",
            )

        # Alte RTMP-Slots zunächst weiterhin einlesen.
        if "rtmp_inputs" not in data:
            data["rtmp_inputs"] = []
            input_config = data.get("input", {})
            input_url = input_config.get("url")
            if input_config.get("type") == "rtmp" and input_url:
                from urllib.parse import urlparse

                path = urlparse(input_url).path.strip("/")
                if path:
                    data["rtmp_inputs"].append({
                        "id": "quelle-1",
                        "name": "Quelle 1",
                        "path": path,
                        "viewer_path": (
                            data.get("stream", {}).get("name")
                            if input_config.get("mode") == "copy_repair"
                            else None
                        ),
                        "enabled": True,
                    })

        # Migration: Hauptquelle und zusätzliche RTMP-Slots werden einmalig
        # in eine gemeinsame Liste gleichwertiger Quellen überführt.
        # Ältere Dateien enthielten teils bereits `sources: []`, obwohl die
        # Hauptquelle noch migriert werden musste. Neu gespeicherte Dateien
        # tragen deshalb einen expliziten Marker, damit eine bewusst geleerte
        # Quellenliste nicht wieder aufgefüllt wird.
        sources_configured = bool(
            data.get("sources_configured", False)
        )
        if (
            "sources" not in data
            or (
                not data.get("sources")
                and not sources_configured
            )
        ):
            sources: list[dict] = []
            input_config = data.get("input", {})
            stream_config = data.get("stream", {})
            source_profile = data.get("source_profile")

            profile = {
                "rtmp_passthrough": "direct",
                "rtmp_repair": "copy_repair",
                "capture_card": "transcode",
            }.get(
                source_profile,
                (
                    "copy_repair"
                    if input_config.get("mode") == "copy_repair"
                    else (
                        "direct"
                        if input_config.get("type") in {"rtmp", "rtsp"}
                        else "transcode"
                    )
                ),
            )

            primary_id = "quelle-1"
            if input_config.get("type") == "rtmp":
                from urllib.parse import urlparse

                path = urlparse(input_config.get("url") or "").path.strip("/")
                matching = next(
                    (
                        item
                        for item in data.get("rtmp_inputs", [])
                        if item.get("path") == path
                    ),
                    None,
                )
                if matching:
                    primary_id = matching.get("id", primary_id)

            sources.append({
                "id": primary_id,
                "name": "Quelle 1",
                "type": input_config.get("type", "v4l2"),
                "profile": profile,
                "enabled": True,
                "url": input_config.get("url"),
                "device": input_config.get("device"),
                "width": input_config.get("width", 1280),
                "height": input_config.get("height", 720),
                "fps": input_config.get("fps", 30),
                "format": input_config.get("format", "mjpeg"),
                "transport": input_config.get("transport", "tcp"),
                "codec": data.get("encoder", {}).get("codec"),
                # Bestehende Installationen behalten ihr bisheriges Audio.
                "audio_mode": "copy",
            })

            known_ids = {primary_id}
            for item in data.get("rtmp_inputs", []):
                item_id = item.get("id")
                if not item_id or item_id in known_ids:
                    continue
                sources.append({
                    "id": item_id,
                    "name": item.get("name") or item_id,
                    "type": "rtmp",
                    "profile": (
                        "copy_repair"
                        if item.get("viewer_path")
                        else "direct"
                    ),
                    "enabled": item.get("enabled", True),
                    "audio_mode": "copy",
                })
                known_ids.add(item_id)

            data["sources"] = sources[:8]

        publisher_tokens_need_migration = any(
            source.get("type") == "rtmp"
            and len(str(source.get("publish_token") or "").strip()) != 12
            for source in data.get("sources", [])
        )
        config = AppConfig(**data)
        if publisher_tokens_need_migration:
            # Einmalige Migration: MediaMTX liest den Token bei jeder
            # Publish-Anmeldung neu aus der Laufzeitkonfiguration.
            self._save_to(self.config_file, config)
        return config

    def save(
        self,
        config: AppConfig,
    ) -> None:
        self._save_to(self.config_file, config)

    @staticmethod
    def _save_to(path: Path, config: AppConfig) -> None:

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = config.model_dump()
        data["sources_configured"] = True

        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            text=True,
        )
        temporary_path = Path(temporary)

        try:
            with os.fdopen(
                descriptor,
                "w",
                encoding="utf-8",
            ) as file:
                yaml.safe_dump(
                    data,
                    file,
                    allow_unicode=True,
                    sort_keys=False,
                )
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)

    @property
    def last_known_good_file(self) -> Path:
        return self.config_file.with_name(
            f"{self.config_file.stem}.last-known-good"
            f"{self.config_file.suffix}"
        )

    def save_last_known_good(self, config: AppConfig) -> None:
        self._save_to(self.last_known_good_file, config)

    def load_last_known_good(self) -> AppConfig:
        loader = ConfigLoader(str(self.last_known_good_file))
        return loader.load()
