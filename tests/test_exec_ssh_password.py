import json

import pytest

from nanobot.agent.tools.exec_transport import ExecTarget
from nanobot.agent.tools.shell import ExecTool


def test_exec_expect_script_escapes_password_prompt_pattern() -> None:
    tool = ExecTool()

    script = tool._build_expect_ssh_script()

    assert r".*\[Pp\]assword:.*" in script


def test_exec_strips_expect_transport_noise_from_password_ssh_result() -> None:
    tool = ExecTool()

    cleaned = tool._strip_expect_transport_noise(
        "spawn ssh -p 2223 nanobot@127.0.0.1 echo ok\r\n\r\n"
        "nanobot@127.0.0.1's password: \r\n"
        "ok-from-password-exectool\r\n"
        "Connection to 127.0.0.1 closed by remote host.\r\n",
        ExecTarget(kind="ssh", host="127.0.0.1", port=2223, username="nanobot"),
    )

    assert "spawn ssh" not in cleaned
    assert "password:" not in cleaned
    assert "closed by remote host" not in cleaned
    assert "ok-from-password-exectool" in cleaned


@pytest.mark.asyncio
async def test_exec_remote_password_is_not_echoed_in_result(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("NANOBOT_SSH_PASSWORD", raising=False)
    tool = ExecTool(working_dir=str(tmp_path))

    async def fake_remote(*, target, command, timeout, env):
        assert env["NANOBOT_SSH_PASSWORD"] == "secret-123"
        return "ok"

    monkeypatch.setattr(tool, "_run_remote_command", fake_remote)
    result = await tool.execute(
        command="uptime",
        target="root@example-host",
        ssh_password="secret-123",
    )

    assert "secret-123" not in result


@pytest.mark.asyncio
async def test_exec_remote_password_is_redacted_from_audit(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("NANOBOT_SSH_PASSWORD", raising=False)
    tool = ExecTool(working_dir=str(tmp_path))

    async def fake_remote(*, target, command, timeout, env):
        return "ok"

    monkeypatch.setattr(tool, "_run_remote_command", fake_remote)
    await tool.execute(
        command="uptime",
        target="root@example-host",
        ssh_password="secret-123",
    )

    payload = json.loads((tmp_path / "audit" / "commands.jsonl").read_text().splitlines()[-1])
    assert "secret-123" not in payload["detail"]
    assert "secret-123" not in payload["command"]
