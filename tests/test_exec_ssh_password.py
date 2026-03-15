import json

import pytest

from nanobot.agent.tools.shell import ExecTool


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
