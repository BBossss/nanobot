import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.agent.context import ContextBuilder
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
async def test_run_agent_loop_still_emits_action_and_heartbeat_after_feedback_extraction(
    tmp_path: Path,
) -> None:
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
    assert any("正在读取日志" in item for item in progress)
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


@pytest.mark.asyncio
async def test_paused_session_short_circuits_without_new_investigation_tool_calls(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path, max_rounds=4)
    loop.provider.chat = AsyncMock(side_effect=AssertionError("provider should not be called while paused"))
    loop.tools.execute = AsyncMock(side_effect=AssertionError("tools should not be called while paused"))

    await loop.process_direct("暂停", session_key="cli:paused")
    result = await loop.process_direct("继续查一下", session_key="cli:paused")

    assert "暂停" in result
    assert loop.provider.chat.await_count == 0
    assert loop.tools.execute.await_count == 0


@pytest.mark.asyncio
async def test_workflow_result_mode_injects_bounded_runtime_context_without_changing_tool_calls(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path, max_rounds=4)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="先看日志。",
                tool_calls=[ToolCallRequest(id="1", name="read_log_tail", arguments={"path": "/var/log/app.log"})],
            ),
            LLMResponse(content="根因已确认，就是日志轮转失败。", tool_calls=[]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="log evidence")
    session = loop.sessions.get_or_create("cli:investigation")
    session.metadata["workflow_result_mode"] = "evidence_first"
    session.metadata["workflow_result_mode_reason"] = "先别急着下结论"
    loop.sessions.save(session)

    final_content = await loop.process_direct("storage 集群出问题了", session_key="cli:investigation")

    assert final_content
    assert loop.tools.execute.await_count == 1
    first_call_messages = loop.provider.chat.await_args_list[0].kwargs["messages"]
    runtime_contexts = [
        str(message["content"])
        for message in first_call_messages
        if message.get("role") == "user"
        and isinstance(message.get("content"), str)
        and str(message["content"]).startswith(ContextBuilder._RUNTIME_CONTEXT_TAG)
    ]
    assert len(runtime_contexts) == 2
    workflow_context = next(item for item in runtime_contexts if "Workflow Controls:" in item)
    assert "证据优先收口" in workflow_context
    assert "结果收口" in workflow_context
    assert "调查动作选择仍然是判断" in workflow_context or "investigation choice remains judgment-based" in workflow_context
    assert "read_log_tail" in str(first_call_messages)


@pytest.mark.asyncio
async def test_workflow_result_mode_applies_to_followup_troubleshooting_turn_after_enable(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path, max_rounds=4)
    loop.provider.chat = AsyncMock(
        return_value=LLMResponse(
            content="已确认事实：日志里连续报错；关键证据：node-a 上的 logrotate 报错。根因已确认，就是日志轮转失败。",
            tool_calls=[],
        )
    )
    session = loop.sessions.get_or_create("cli:investigation")
    session.metadata["workflow_result_mode"] = "evidence_first"
    session.metadata["workflow_result_mode_reason"] = "先别急着下结论"
    loop.sessions.save(session)

    result = await loop.process_direct("storage 集群出问题了", session_key="cli:investigation")

    assert result.startswith("已确认事实：")
    assert result.index("已确认事实：") < result.index("当前倾向")
    assert "根因已确认" not in result
    assert "不确定点" in result
    assert "下一步" in result


@pytest.mark.asyncio
async def test_resume_allows_investigation_to_continue_from_existing_session_context(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path, max_rounds=4)
    provider_calls: list[list[dict]] = []

    async def _chat(*, messages, **_kwargs):
        provider_calls.append(messages)
        if len(provider_calls) == 1:
            return LLMResponse(
                content="先看日志。",
                tool_calls=[ToolCallRequest(id="1", name="read_log_tail", arguments={"path": "/var/log/app.log"})],
            )
        if len(provider_calls) == 2:
            return LLMResponse(content="初步看完了日志。", tool_calls=[])
        if len(provider_calls) == 3:
            tool_messages = [m for m in messages if m.get("role") == "tool"]
            assistant_messages = [m for m in messages if m.get("role") == "assistant"]
            assert any("line1\nline2" in str(m.get("content")) for m in tool_messages)
            assert any("初步看完了日志。" in str(m.get("content")) for m in assistant_messages)
            return LLMResponse(content="继续调查。", tool_calls=[])
        raise AssertionError("unexpected provider call")

    loop.provider.chat = AsyncMock(side_effect=_chat)
    loop.tools.execute = AsyncMock(return_value="line1\nline2")

    first = await loop.process_direct("应用报错了", session_key="cli:resume")
    paused = await loop.process_direct("暂停", session_key="cli:resume")
    resumed = await loop.process_direct("继续", session_key="cli:resume")
    second = await loop.process_direct("还有别的线索吗", session_key="cli:resume")

    assert "继续调查" in second
    assert "暂停" in paused
    assert "继续" in resumed
    assert loop.tools.execute.await_count == 1
    assert first


@pytest.mark.asyncio
async def test_不要多节点_blocks_confirmed_multi_target_reuse_in_later_investigation(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path, max_rounds=4)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="继续查服务状态。",
                tool_calls=[ToolCallRequest(id="1", name="service_status", arguments={"service": "nginx"})],
            ),
            LLMResponse(content="调查完成。", tool_calls=[]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="active")
    session = loop.sessions.get_or_create("cli:scope")
    session.metadata["expansion_confirmed"] = True
    session.metadata["resolved_target_ids"] = ["node-a", "node-b"]
    session.metadata["resolved_targets"] = [
        {"id": "node-a", "target": "root@10.0.0.1", "labels": ["storage"]},
        {"id": "node-b", "target": "root@10.0.0.2", "labels": ["storage"]},
    ]
    session.metadata["resolution_reason"] = "storage 集群都需要看"
    loop.sessions.save(session)

    await loop.process_direct("不要多节点", session_key="cli:scope")
    result = await loop.process_direct("继续查一下", session_key="cli:scope")

    assert "调查完成" in result
    loop.tools.execute.assert_awaited_once_with("service_status", {"service": "nginx"})


@pytest.mark.asyncio
async def test_只查日志_injects_bounded_focus_hint_for_later_investigation_planning(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path, max_rounds=4)
    provider_calls: list[list[dict]] = []

    async def _chat(*, messages, **_kwargs):
        provider_calls.append(messages)
        if len(provider_calls) == 1:
            return LLMResponse(
                content="先按日志方向检查。",
                tool_calls=[ToolCallRequest(id="1", name="read_log_tail", arguments={"path": "/var/log/app.log"})],
            )
        if len(provider_calls) == 2:
            return LLMResponse(content="日志里先看到异常。", tool_calls=[])
        raise AssertionError("unexpected provider call")

    loop.provider.chat = AsyncMock(side_effect=_chat)
    loop.tools.execute = AsyncMock(return_value="timeout error")

    await loop.process_direct("只查日志", session_key="cli:focus")
    result = await loop.process_direct("帮我继续排查", session_key="cli:focus")

    assert "日志里先看到异常" in result
    prompt_texts = [
        str(message.get("content"))
        for message in provider_calls[0]
        if message.get("role") == "user"
    ]
    assert any("logs_only" in text or "只查日志" in text or "优先日志" in text for text in prompt_texts)
    assert all("必须只执行日志工具" not in text for text in prompt_texts)
