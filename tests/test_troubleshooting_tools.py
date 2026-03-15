from unittest.mock import MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.agent.tools.troubleshooting import _build_target_runner
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import TroubleshootingToolConfig


def test_troubleshooting_tool_config_defaults() -> None:
    cfg = TroubleshootingToolConfig()

    assert cfg.enabled is True
    assert "/sf/log" in cfg.allowed_log_roots
    assert cfg.default_tail_lines == 200
    assert cfg.max_recent_files == 50


def test_agent_loop_registers_troubleshooting_tools(tmp_path) -> None:
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="test-model",
    )

    assert loop.tools.get("find_logs") is not None
    assert loop.tools.get("read_log_tail") is not None
    assert loop.tools.get("service_status") is not None


def test_target_runner_parses_local_and_remote_targets() -> None:
    runner = _build_target_runner(default_target="local", ssh_enabled=True)

    assert runner.parse_target("local").kind == "local"
    assert runner.parse_target("ops@host-a:2222").host == "host-a"


@pytest.mark.asyncio
async def test_target_runner_rejects_raw_ssh_command() -> None:
    runner = _build_target_runner(default_target="local", ssh_enabled=True)

    result = await runner.run(command="ssh root@host-a uptime", target="local")

    assert "Use target=" in result
