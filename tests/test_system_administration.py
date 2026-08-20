from open_bos_stream.core.process import ProcessResult
from open_bos_stream.system.administration import (
    REBOOT_HELPER,
    STREAM_LOG_HELPER,
    SystemAdministrationService,
)


class FakeRunner:
    def __init__(self, stdout: str = "") -> None:
        self.stdout = stdout
        self.commands: list[list[str]] = []

    def run(self, command, **kwargs):
        self.commands.append(list(command))
        return ProcessResult(
            command=tuple(command),
            returncode=0,
            stdout=self.stdout,
            stderr="",
            duration=0.01,
        )


def test_stream_log_uses_fixed_helper_and_redacts_secrets() -> None:
    runner = FakeRunner(
        "publish rtmp://admin:secret@example/live?id=1&token=abc123\n"
        "publish_token: top-secret\n"
    )
    service = SystemAdministrationService(runner)

    log = service.stream_log()

    assert runner.commands == [["sudo", STREAM_LOG_HELPER]]
    assert "secret" not in log
    assert "abc123" not in log
    assert "top-secret" not in log
    assert "token=***" in log


def test_reboot_uses_fixed_helper_without_parameters() -> None:
    runner = FakeRunner()
    service = SystemAdministrationService(runner)

    service.schedule_reboot()

    assert runner.commands == [["sudo", REBOOT_HELPER]]
