from open_bos_stream.core.config import ConfigLoader

loader = ConfigLoader()

config = loader.load()

print(config)

loader.save(config)

print("OK")
