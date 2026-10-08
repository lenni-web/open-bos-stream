from open_bos_stream.core.process import ProcessResult
from open_bos_stream.system.info import SystemInfoService


class CountingRunner:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def run(self, command, **_kwargs) -> ProcessResult:
        args = tuple(command)
        self.commands.append(args)
        if args[0] == "ffmpeg":
            output = "ffmpeg version 7.1\n"
        elif args[-1] == "--version":
            output = "v1.19.3\n"
        else:
            output = '"Debian GNU/Linux"\n'

        return ProcessResult(args, 0, output, "", 0.0)


def test_static_system_information_is_cached() -> None:
    runner = CountingRunner()
    service = SystemInfoService(runner)

    first = service.info()
    second = service.info()

    assert first is second
    assert runner.commands.count(("ffmpeg", "-version")) == 1
    assert runner.commands.count(("lsb_release", "-ds")) == 1


def test_mediamtx_version_is_reported() -> None:
    info = SystemInfoService(CountingRunner()).info()

    assert info.runtime.mediamtx == "v1.19.3"


def test_missing_mediamtx_is_reported_as_unknown() -> None:
    class FailingRunner(CountingRunner):
        def run(self, command, **kwargs) -> ProcessResult:
            if tuple(command)[-1] == "--version":
                raise RuntimeError("nicht installiert")
            return super().run(command, **kwargs)

    info = SystemInfoService(FailingRunner()).info()

    assert info.runtime.mediamtx == "Unknown"
