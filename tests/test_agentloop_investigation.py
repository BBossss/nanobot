import asyncio
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
async def test_run_agent_loop_stops_after_max_investigation_rounds(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path, max_rounds=2)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(content="", tool_calls=[ToolCallRequest(id="1", name="exec", arguments={"command": "uptime"})]),
            LLMResponse(content="", tool_calls=[ToolCallRequest(id="2", name="exec", arguments={"command": "date"})]),
            LLMResponse(content="", tool_calls=[ToolCallRequest(id="3", name="exec", arguments={"command": "whoami"})]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="ok")

    final_content, _tools_used, _messages = await loop._run_agent_loop(
        [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}]
    )

    assert final_content is not None
    assert "maximum investigation rounds (2)" in final_content
    assert loop.provider.chat.await_count == 2


@pytest.mark.asyncio
async def test_run_agent_loop_reuses_repeated_tool_results(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path, max_rounds=4)
    repeated = ToolCallRequest(id="1", name="exec", arguments={"command": "uptime", "target": "host-a"})
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(content="", tool_calls=[repeated]),
            LLMResponse(
                content="",
                tool_calls=[ToolCallRequest(id="2", name="exec", arguments={"command": "uptime", "target": "host-a"})],
            ),
            LLMResponse(content="done", tool_calls=[]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="same-evidence")

    final_content, _tools_used, messages = await loop._run_agent_loop(
        [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}]
    )

    assert final_content == "done"
    assert loop.tools.execute.await_count == 1
    tool_messages = [m["content"] for m in messages if m.get("role") == "tool"]
    assert any("no new evidence" in str(content).lower() for content in tool_messages)


@pytest.mark.asyncio
async def test_run_agent_loop_converges_after_two_stale_rounds(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path, max_rounds=8)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(content="", tool_calls=[ToolCallRequest(id="1", name="exec", arguments={"command": "uptime"})]),
            LLMResponse(content="", tool_calls=[ToolCallRequest(id="2", name="exec", arguments={"command": "uptime"})]),
            LLMResponse(content="", tool_calls=[ToolCallRequest(id="3", name="exec", arguments={"command": "uptime"})]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="same-evidence")

    final_content, _tools_used, _messages = await loop._run_agent_loop(
        [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}]
    )

    assert final_content is not None
    assert "two consecutive rounds produced no new evidence" in final_content
    assert loop.tools.execute.await_count == 1
    assert loop.provider.chat.await_count == 3


@pytest.mark.asyncio
async def test_run_agent_loop_emits_stage_progress_messages(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path, max_rounds=4)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="先检查日志。",
                tool_calls=[ToolCallRequest(id="1", name="read_log_tail", arguments={"path": "/var/log/app.log"})],
            ),
            LLMResponse(content="已完成结论。", tool_calls=[]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="ok")
    progress: list[str] = []

    final_content, _tools_used, _messages = await loop._run_agent_loop(
        [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}],
        on_progress=AsyncMock(side_effect=lambda content, **_: progress.append(content)),
    )

    assert final_content == "已完成结论。"
    assert any("生成调查计划" in item for item in progress)
    assert any("执行只读检查" in item for item in progress)
    assert any("汇总证据" in item for item in progress)
    assert any("输出判断" in item for item in progress)


@pytest.mark.asyncio
async def test_run_agent_loop_emits_action_and_reason_feedback(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path, max_rounds=4)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="日志里有 timeout。",
                tool_calls=[ToolCallRequest(id="1", name="read_log_tail", arguments={"path": "/var/log/app.log"})],
            ),
            LLMResponse(
                content="继续确认服务状态。",
                tool_calls=[ToolCallRequest(id="2", name="service_status", arguments={"service": "nginx"})],
            ),
            LLMResponse(content="结论完成。", tool_calls=[]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="ok")
    progress: list[str] = []

    final_content, _tools_used, _messages = await loop._run_agent_loop(
        [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}],
        on_progress=AsyncMock(side_effect=lambda content, **_: progress.append(content)),
    )

    assert final_content == "结论完成。"
    assert any("正在读取日志" in item for item in progress)
    assert any("正在检查服务状态" in item for item in progress)
    assert any("所以先读取日志" in item for item in progress)
    assert any("所以再检查服务状态" in item for item in progress)


@pytest.mark.asyncio
async def test_run_agent_loop_emits_process_summary_before_final_answer(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path, max_rounds=4)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="先看日志。",
                tool_calls=[ToolCallRequest(id="1", name="read_log_tail", arguments={"path": "/var/log/app.log"})],
            ),
            LLMResponse(
                content="再看服务状态。",
                tool_calls=[ToolCallRequest(id="2", name="service_status", arguments={"service": "nginx"})],
            ),
            LLMResponse(content="最终结论。", tool_calls=[]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="ok")
    progress: list[str] = []

    final_content, _tools_used, _messages = await loop._run_agent_loop(
        [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}],
        on_progress=AsyncMock(side_effect=lambda content, **_: progress.append(content)),
    )

    assert final_content == "最终结论。"
    summary_index = next(i for i, item in enumerate(progress) if "刚才先检查了" in item)
    output_index = next(i for i, item in enumerate(progress) if item == "输出判断")
    assert summary_index < output_index


@pytest.mark.asyncio
async def test_run_agent_loop_emits_heartbeat_for_slow_tool_calls(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path, max_rounds=4)
    loop._PROGRESS_HEARTBEAT_INITIAL_S = 0.01
    loop._PROGRESS_HEARTBEAT_INTERVAL_S = 0.01
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="先看日志。",
                tool_calls=[ToolCallRequest(id="1", name="read_log_tail", arguments={"path": "/var/log/app.log"})],
            ),
            LLMResponse(content="最终结论。", tool_calls=[]),
        ]
    )

    async def _slow_execute(*_args, **_kwargs) -> str:
        await asyncio.sleep(0.03)
        return "ok"

    loop.tools.execute = AsyncMock(side_effect=_slow_execute)
    progress: list[str] = []

    final_content, _tools_used, _messages = await loop._run_agent_loop(
        [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}],
        on_progress=AsyncMock(side_effect=lambda content, **_: progress.append(content)),
    )

    assert final_content == "最终结论。"
    assert any("仍在读取日志" in item for item in progress)


@pytest.mark.asyncio
async def test_await_tool_with_heartbeat_does_not_leak_shielded_future_exception(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path, max_rounds=4)
    loop._PROGRESS_HEARTBEAT_INITIAL_S = 0.01
    loop._PROGRESS_HEARTBEAT_INTERVAL_S = 0.01

    async def _slow_fail(*_args, **_kwargs) -> str:
        await asyncio.sleep(0.03)
        raise RuntimeError("boom")

    loop.tools.execute = AsyncMock(side_effect=_slow_fail)
    progress: list[str] = []
    exception_contexts: list[dict] = []
    event_loop = asyncio.get_running_loop()
    original_handler = event_loop.get_exception_handler()
    event_loop.set_exception_handler(lambda _loop, context: exception_contexts.append(context))

    try:
        with pytest.raises(RuntimeError, match="boom"):
            await loop._await_tool_with_heartbeat(
                "read_log_tail",
                {"path": "/var/log/app.log"},
                session=None,
                on_progress=AsyncMock(side_effect=lambda content, **_: progress.append(content)),
                multi_target_total=1,
            )
        await asyncio.sleep(0)
    finally:
        event_loop.set_exception_handler(original_handler)

    assert any("仍在读取日志" in item for item in progress)
    assert exception_contexts == []
