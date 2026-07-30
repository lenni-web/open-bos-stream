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

        # Migration: Der bisherige einzelne RTMP-Eingang wird zum ersten
        # Mehrquellen-Slot. Eine bewusst gespeicherte leere Liste bleibt leer.
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

        return AppConfig(**data)

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
