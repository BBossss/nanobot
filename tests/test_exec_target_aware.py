import pytest

from nanobot.config.schema import ExecToolConfig
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.exec_transport import parse_exec_target


def test_exec_tool_config_exposes_target_aware_defaults() -> None:
    cfg = ExecToolConfig()

    assert cfg.default_target == "local"
    assert cfg.max_investigation_rounds == 8
    assert cfg.ssh.enabled is True


def test_parse_exec_target_for_local() -> None:
    target = parse_exec_target("local")

    assert target.kind == "local"
    assert target.host == ""


def test_parse_exec_target_for_remote_host() -> None:
    target = parse_exec_target("root@example-host:2222")

    assert target.kind == "ssh"
    assert target.username == "root"
    assert target.host == "example-host"
    assert target.port == 2222


@pytest.mark.asyncio
async def test_exec_runs_local_when_target_is_local(tmp_path) -> None:
    tool = ExecTool(working_dir=str(tmp_path))

    result = await tool.execute(command="printf 'ok'", target="local")

    assert "ok" in result


@pytest.mark.asyncio
async def test_exec_rejects_raw_ssh_in_command_string(tmp_path) -> None:
    tool = ExecTool(timeout=1, working_dir=str(tmp_path))

    result = await tool.execute(
        command="ssh root@example-host 'uptime'",
        target="local",
    )

    assert "Use target=" in result


@pytest.mark.asyncio
async def test_exec_routes_remote_target_to_ssh_transport(tmp_path, monkeypatch) -> None:
    tool = ExecTool(working_dir=str(tmp_path))

    async def fake_run_remote(*, target, command, timeout, env):
        return "remote-ok"

    monkeypatch.setattr(tool, "_run_remote_command", fake_run_remote, raising=False)
    result = await tool.execute(command="uptime", target="root@example-host")

    assert result == "remote-ok"
