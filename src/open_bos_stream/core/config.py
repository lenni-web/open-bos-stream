from pathlib import Path

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

        return AppConfig(**data)

    def save(
        self,
        config: AppConfig,
    ) -> None:

        self.config_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = config.model_dump()

        with self.config_file.open(
            "w",
            encoding="utf-8",
        ) as file:

            yaml.safe_dump(
                data,
                file,
                allow_unicode=True,
                sort_keys=False,
            )
