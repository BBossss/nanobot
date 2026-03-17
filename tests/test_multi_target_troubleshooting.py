from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.agent.multi_target import aggregate_multi_target_results
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import ExecToolConfig
from nanobot.providers.base import LLMResponse, ToolCallRequest
from nanobot.session.manager import Session


def _make_loop(tmp_path: Path) -> AgentLoop:
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    return AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        exec_config=ExecToolConfig(max_investigation_rounds=4),
    )


def _confirmed_session() -> Session:
    session = Session(key="cli:direct")
    session.metadata["expansion_confirmed"] = True
    session.metadata["resolved_targets"] = [
        {"id": "node-a", "target": "root@10.0.0.1", "labels": ["storage"]},
        {"id": "node-b", "target": "root@10.0.0.2", "labels": ["storage"]},
    ]
    return session


@pytest.mark.asyncio
async def test_run_agent_loop_fans_out_supported_troubleshooting_tool(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    session = _confirmed_session()
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="",
                tool_calls=[ToolCallRequest(id="1", name="service_status", arguments={"service": "nginx"})],
            ),
            LLMResponse(content="done", tool_calls=[]),
        ]
    )

    async def _exec(name: str, params: dict) -> str:
        return f"[target={params['target']}] {name}({params.get('service', '')})"

    loop.tools.execute = AsyncMock(side_effect=_exec)

    final_content, _tools_used, messages = await loop._run_agent_loop(
        [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}],
        session=session,
    )

    assert final_content == "done"
    assert loop.tools.execute.await_count == 2
    targets = [call.args[1]["target"] for call in loop.tools.execute.await_args_list]
    assert targets == ["root@10.0.0.1", "root@10.0.0.2"]
    tool_messages = [m["content"] for m in messages if m.get("role") == "tool"]
    assert any("node-a" in str(content) for content in tool_messages)
    assert any("node-b" in str(content) for content in tool_messages)


@pytest.mark.asyncio
async def test_run_agent_loop_keeps_unsupported_tools_single_target(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    session = _confirmed_session()
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="",
                tool_calls=[ToolCallRequest(id="1", name="exec", arguments={"command": "uptime"})],
            ),
            LLMResponse(content="done", tool_calls=[]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="ok")

    final_content, _tools_used, _messages = await loop._run_agent_loop(
        [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}],
        session=session,
    )

    assert final_content == "done"
    assert loop.tools.execute.await_count == 1
    assert loop.tools.execute.await_args_list[0].args[1] == {"command": "uptime"}


def test_aggregate_multi_target_results_groups_common_local_and_failures() -> None:
    summary = aggregate_multi_target_results(
        tool_name="service_status",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": "[target=root@10.0.0.1] active",
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": "[target=root@10.0.0.2] active",
            },
            {
                "target_id": "node-c",
                "target_host": "root@10.0.0.3",
                "status": "error",
                "content": "",
                "error": "timeout",
            },
        ],
    )

    assert "Common Findings" in summary
    assert "node-a, node-b" in summary
    assert "active" in summary
    assert "Failed Targets" in summary
    assert "node-c: timeout" in summary


def test_aggregate_multi_target_results_includes_log_timeline_for_log_tools() -> None:
    summary = aggregate_multi_target_results(
        tool_name="search_log",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] Found matches in /sf/log/app.log:\n"
                    "12: 2026-03-18 10:21:03 timeout while connecting"
                ),
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.2] Found matches in /sf/log/app.log:\n"
                    "18: 2026-03-18 10:21:05 timeout while connecting"
                ),
            },
        ],
    )

    assert "Timeline" in summary
    assert "10:21:03 node-a" in summary
    assert "Concurrent / Near Events" in summary


def test_aggregate_multi_target_results_lists_unknown_log_lines_without_fake_timeline() -> None:
    summary = aggregate_multi_target_results(
        tool_name="read_log_tail",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] tail 1 lines from /sf/log/app.log:\n"
                    "timeout while connecting"
                ),
            },
        ],
    )

    assert "Timeline" not in summary
    assert "No Timestamp Evidence" in summary


def test_aggregate_multi_target_results_keeps_non_log_tools_without_timeline() -> None:
    summary = aggregate_multi_target_results(
        tool_name="service_status",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": "[target=root@10.0.0.1] service_status(nginx)\nactive (running)",
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": "[target=root@10.0.0.2] service_status(nginx)\nactive (running)",
            },
        ],
    )

    assert "Timeline" not in summary
    assert "Common Findings" in summary
