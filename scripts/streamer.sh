#!/bin/bash

set -e

cd /opt/open-bos-stream

exec ffmpeg \
    -hide_banner \
    -loglevel warning \
    -f v4l2 \
    -thread_queue_size 512 \
    -input_format mjpeg \
    -video_size 1280x720 \
    -framerate 30 \
    -i /dev/video0 \
    -c:v libx264 \
    -pix_fmt yuv420p \
    -preset veryfast \
    -tune zerolatency \
    -b:v 4M \
    -f rtsp \
    rtsp://127.0.0.1:8554/drohne
