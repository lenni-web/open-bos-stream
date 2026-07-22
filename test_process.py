from time import sleep

from open_bos_stream.stream.process import FFmpegProcess

process = FFmpegProcess()

process.start(["sleep", "30"])

print("Running:", process.running)
print("PID:", process.pid)

sleep(3)

process.stop()

print("Running:", process.running)
