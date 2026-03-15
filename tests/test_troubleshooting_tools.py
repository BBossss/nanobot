from unittest.mock import MagicMock

from nanobot.agent.loop import AgentLoop
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
