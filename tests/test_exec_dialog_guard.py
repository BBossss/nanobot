from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import ExecToolConfig
from nanobot.providers.base import LLMResponse, ToolCallRequest


def _make_loop(tmp_path: Path) -> AgentLoop:
    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    return AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        memory_window=10,
        exec_config=ExecToolConfig(
            readonly_mode=True,
            approval_file=str(tmp_path / "approvals.json"),
        ),
    )


@pytest.mark.asyncio
async def test_exec_guard_still_blocks_after_user_confirms_continue(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    calls = iter([
        LLMResponse(content="这是高风险操作，请确认是否继续。", tool_calls=[]),
        LLMResponse(
            content="",
            tool_calls=[
                ToolCallRequest(
                    id="call-1",
                    name="exec",
                    arguments={"command": "launchctl stop com.apple.Finder"},
                )
            ],
        ),
        LLMResponse(content="工具层已阻止该高风险命令。", tool_calls=[]),
    ])
    loop.provider.chat = AsyncMock(side_effect=lambda *a, **kw: next(calls))

    first = await loop._process_message(
        InboundMessage(channel="cli", sender_id="user", chat_id="direct", content="请执行命令：launchctl stop com.apple.Finder")
    )
    assert first is not None
    assert "请确认是否继续" in first.content

    second = await loop._process_message(
        InboundMessage(channel="cli", sender_id="user", chat_id="direct", content="继续")
    )
    assert second is not None
    assert "阻止" in second.content

    audit_file = tmp_path / "audit" / "commands.jsonl"
    assert audit_file.exists()
    payload = audit_file.read_text(encoding="utf-8").splitlines()[-1]
    assert '"status": "blocked"' in payload
    assert 'launchctl stop com.apple.Finder' in payload
