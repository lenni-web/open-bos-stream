from __future__ import annotations

from open_bos_stream.core.models import SourceConfig

from .base import InputBuilder
from .registry import registry
from .device_manager import (
    DeviceManager,
)

from .v4l2_detect import (
    V4L2Detector,
)

from open_bos_stream.stream.video_formats import (
    VideoFormat,
)

class V4L2InputBuilder(InputBuilder):

    type = "v4l2"

    name = "Capture Card"

    fields = [

        {
            "name": "device",
            "label": "Gerät",
            "widget": "text",
        },

        {
            "name": "width",
            "label": "Breite",
            "widget": "number",
        },

        {
            "name": "height",
            "label": "Höhe",
            "widget": "number",
        },

        {
            "name": "fps",
            "label": "FPS",
            "widget": "number",
        },

        {
            "name": "format",
            "label": "Format",
            "widget": "select",
            "options": [],
            "default": "mjpeg",
        },

    ]

    def capability_fields(
        self,
    ) -> list[str]:

        return [

            "device",

            "format",

        ]

    def output_formats(
        self,
        source: SourceConfig,
    ) -> list[VideoFormat]:

        try:

            return [

                VideoFormat(
                    source.format,
                ),

            ]

        except ValueError:

            return []

    def build(
        self,
        source: SourceConfig,
    ) -> list[str]:

        return [

            "-f",
            "v4l2",

            "-thread_queue_size",
            "512",

            "-input_format",
            source.format,

            "-video_size",
            f"{source.width}x{source.height}",

            "-framerate",
            str(source.fps),

            "-i",
            source.device,

        ]

    def metadata_fields(
        self,
    ) -> list[dict]:

        fields: list[dict] = []

        devices = (
            DeviceManager.video_devices()
        )

        selected_device = (

            devices[0].path

            if devices

            else "/dev/video0"

        )

        for field in self.fields:

            item = field.copy()

            if item["name"] == "device":

                item["widget"] = "select"

                item["options"] = [

                    {

                        "value": device.path,

                        "label": device.name,

                    }

                    for device in devices

                ]

            elif item["name"] == "format":

                device = next(

                    (

                        d

                        for d in devices

                        if d.path == selected_device

                    ),

                    None,

                )

                item["options"] = (

                    [

                        fmt.value

                        for fmt in device.formats

                    ]

                    if device

                    else []

                )

            fields.append(
                item,
            )

        return fields

registry.register(
    V4L2InputBuilder(),
)