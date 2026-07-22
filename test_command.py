from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.stream.command import FFmpegCommandBuilder

config = ConfigLoader().load()

builder = FFmpegCommandBuilder(config)

print("===== Ohne Recording =====")
print(" ".join(builder.build()))

print()

print("===== Mit Recording =====")
print(" ".join(builder.build("recordings/test.mp4")))
