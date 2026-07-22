from open_bos_stream.recording.service import RecordingService

service = RecordingService()

print(service.status)

print(service.prepare())

service.start()

print(service.status)

service.stop()

print(service.status)
