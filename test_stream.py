from time import sleep

from open_bos_stream.core.config import ConfigLoader
from open_bos_stream.stream.service import StreamService

config = ConfigLoader().load()

stream = StreamService(config)

print(stream.running)

stream.start()

sleep(5)

print(stream.running)

print(stream.pid)

stream.stop()

print(stream.running)
