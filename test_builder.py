from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.stream.command import FFmpegCommandBuilder

config = ConfigLoader().load()

builder = FFmpegCommandBuilder(config)

for item in builder.build():
    print(item)
