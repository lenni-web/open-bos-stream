from open_bos_stream.core.process import ProcessResult
from open_bos_stream.web_access.config import WebAccessConfig
from open_bos_stream.web_access.manager import WebAccessManager


class FakeRunner:
    def __init__(self):
        self.active = False
        self.commands = []

    def run(self, command, **kwargs):
        self.commands.append(tuple(command))
        if command[:3] == ["systemctl", "is-active", "--quiet"]:
            return self._result(command, 0 if self.active else 3)
        if command[:4] == ["sudo", "systemctl", "enable", "--now"]:
            self.active = True
        elif command[:4] == ["sudo", "systemctl", "disable", "--now"]:
            self.active = False
        return self._result(command, 0)

    @staticmethod
    def _result(command, returncode):
        return ProcessResult(
            command=tuple(command),
            returncode=returncode,
            stdout="",
            stderr="",
            duration=0,
        )


def test_start_enables_socket_and_stop_disables_it(monkeypatch):
    runner = FakeRunner()
    manager = WebAccessManager(WebAccessConfig(enabled=True), runner)
    monkeypatch.setattr(manager, "_port_occupied", lambda: False)
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    assert manager.start() is True
    assert (
        "sudo",
        "systemctl",
        "enable",
        "--now",
        manager.SOCKET,
    ) in runner.commands

    assert manager.stop() is True
    assert (
        "sudo",
        "systemctl",
        "disable",
        "--now",
        manager.SOCKET,
    ) in runner.commands


def test_start_rejects_an_occupied_standard_port(monkeypatch):
    runner = FakeRunner()
    manager = WebAccessManager(WebAccessConfig(enabled=True), runner)
    monkeypatch.setattr(manager, "_port_occupied", lambda: True)
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    try:
        manager.start()
    except RuntimeError as exc:
        assert "Port 80" in str(exc)
        assert "Port 8000" in str(exc)
    else:
        raise AssertionError("Ein belegter Port 80 muss abgelehnt werden.")


def test_status_reports_conflict_without_removing_fallback(monkeypatch):
    manager = WebAccessManager(WebAccessConfig(enabled=True), FakeRunner())
    monkeypatch.setattr(manager, "_port_occupied", lambda: True)
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    status = manager.status()

    assert status["conflict"] is True
    assert status["fallback_port"] == 8000
    assert "Port 80" in status["error"]
