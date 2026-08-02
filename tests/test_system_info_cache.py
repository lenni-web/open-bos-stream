from open_bos_stream.core.process import ProcessResult
from open_bos_stream.system.info import SystemInfoService


class CountingRunner:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def run(self, command, **_kwargs) -> ProcessResult:
        args = tuple(command)
        self.commands.append(args)
        output = (
            "ffmpeg version 7.1\n"
            if args[0] == "ffmpeg"
            else '"Debian GNU/Linux"\n'
        )
        return ProcessResult(args, 0, output, "", 0.0)


def test_static_system_information_is_cached() -> None:
    runner = CountingRunner()
    service = SystemInfoService(runner)

    first = service.info()
    second = service.info()

    assert first is second
    assert runner.commands.count(("ffmpeg", "-version")) == 1
    assert runner.commands.count(("lsb_release", "-ds")) == 1
