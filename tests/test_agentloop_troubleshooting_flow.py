from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import ExecToolConfig
from nanobot.providers.base import LLMResponse, ToolCallRequest


def _make_loop(tmp_path: Path, *, max_rounds: int = 8) -> AgentLoop:
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    return AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        exec_config=ExecToolConfig(max_investigation_rounds=max_rounds),
    )


@pytest.mark.asyncio
async def test_agent_loop_marks_repeated_log_sampling_as_stale(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path, max_rounds=8)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCallRequest(
                        id="1",
                        name="read_log_tail",
                        arguments={"path": "/sf/log/today/a.log", "target": "host-a", "lines": 200},
                    )
                ],
            ),
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCallRequest(
                        id="2",
                        name="read_log_tail",
                        arguments={"path": "/sf/log/today/a.log", "target": "host-a", "lines": 400},
                    )
                ],
            ),
            LLMResponse(content="done", tool_calls=[]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="[target=host-a] tail output")

    final_content, _tools_used, messages = await loop._run_agent_loop(
        [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}]
    )

    assert final_content == "done"
    assert loop.tools.execute.await_count == 1
    tool_messages = [m["content"] for m in messages if m.get("role") == "tool"]
    assert any("no new evidence" in str(content).lower() for content in tool_messages)
