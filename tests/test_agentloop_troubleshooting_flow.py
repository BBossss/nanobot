from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import ExecToolConfig, TargetingConfig
from nanobot.providers.base import LLMResponse, ToolCallRequest


def _make_loop(
    tmp_path: Path,
    *,
    max_rounds: int = 8,
    targeting: TargetingConfig | None = None,
) -> AgentLoop:
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    return AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        exec_config=ExecToolConfig(max_investigation_rounds=max_rounds),
        targeting=targeting,
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


@pytest.mark.asyncio
async def test_process_direct_suggests_cluster_expansion_without_executing_it(tmp_path: Path) -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1", "labels": ["storage", "hci"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["storage", "hci"]},
            ],
            "groups": [
                {"name": "storage-cluster", "targets": ["node-a", "node-b"]},
            ],
        }
    )
    loop = _make_loop(tmp_path, targeting=targeting)
    loop.provider.chat = AsyncMock(side_effect=AssertionError("provider should not be called"))

    result = await loop.process_direct("storage 集群出问题了", session_key="cli:cluster")

    assert "node-a" in result
    assert "node-b" in result
    assert "确认" in result

    session = loop.sessions.get_or_create("cli:cluster")
    pending = session.metadata.get("pending_target_resolution")
    assert pending is not None
    assert pending["resolved_target_ids"] == ["node-a", "node-b"]
    assert session.metadata.get("expansion_confirmed") is not True


@pytest.mark.asyncio
async def test_process_direct_confirmation_consumes_pending_cluster_expansion(tmp_path: Path) -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1", "labels": ["storage", "hci"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["storage", "hci"]},
            ],
            "groups": [
                {"name": "storage-cluster", "targets": ["node-a", "node-b"]},
            ],
        }
    )
    loop = _make_loop(tmp_path, targeting=targeting)
    loop.provider.chat = AsyncMock(
        return_value=LLMResponse(content="已切换到多节点排查。", tool_calls=[])
    )

    first = await loop.process_direct("storage 集群出问题了", session_key="cli:cluster")
    second = await loop.process_direct("确认", session_key="cli:cluster")

    assert "确认" in first
    assert "多节点" in second
    assert loop.provider.chat.await_count == 1

    session = loop.sessions.get_or_create("cli:cluster")
    assert session.metadata.get("expansion_confirmed") is True
    assert session.metadata.get("resolved_target_ids") == ["node-a", "node-b"]
    assert session.metadata.get("pending_target_resolution") is None


@pytest.mark.asyncio
async def test_process_direct_rejects_cluster_expansion_and_stays_single_target(tmp_path: Path) -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1", "labels": ["storage", "hci"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["storage", "hci"]},
            ],
            "groups": [
                {"name": "storage-cluster", "targets": ["node-a", "node-b"]},
            ],
        }
    )
    loop = _make_loop(tmp_path, targeting=targeting)
    loop.provider.chat = AsyncMock(side_effect=AssertionError("provider should not be called"))

    first = await loop.process_direct("storage 集群出问题了", session_key="cli:cluster")
    second = await loop.process_direct("先单节点", session_key="cli:cluster")

    assert "确认" in first
    assert "单节点" in second

    session = loop.sessions.get_or_create("cli:cluster")
    assert session.metadata.get("pending_target_resolution") is None
    assert session.metadata.get("expansion_confirmed") is False


@pytest.mark.asyncio
async def test_process_direct_emits_confirmed_multi_target_scope_progress(tmp_path: Path) -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1", "labels": ["storage", "hci"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["storage", "hci"]},
            ],
            "groups": [
                {"name": "storage-cluster", "targets": ["node-a", "node-b"]},
            ],
        }
    )
    loop = _make_loop(tmp_path, targeting=targeting)
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content="done", tool_calls=[]))
    progress: list[str] = []

    await loop.process_direct("storage 集群出问题了", session_key="cli:cluster")
    await loop.process_direct(
        "确认",
        session_key="cli:cluster",
        on_progress=AsyncMock(side_effect=lambda content, **_: progress.append(content)),
    )

    assert any("node-a" in item and "node-b" in item for item in progress)
