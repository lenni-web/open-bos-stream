"""
Bekannte Videoformate.
"""

from enum import StrEnum


class VideoFormat(StrEnum):

    MJPEG = "mjpeg"

    H264 = "h264"

    HEVC = "hevc"

    YUYV422 = "yuyv422"

    NV12 = "nv12"