import asyncio
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
async def test_pending_target_expansion_gate_takes_precedence_over_resume_control(tmp_path: Path) -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1", "labels": ["storage", "hci"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["storage", "hci"]},
            ],
            "groups": [{"name": "storage-cluster", "targets": ["node-a", "node-b"]}],
        }
    )
    loop = _make_loop(tmp_path, targeting=targeting)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="先对比 storage 集群。",
                tool_calls=[ToolCallRequest(id="1", name="service_status", arguments={"service": "nginx"})],
            ),
            LLMResponse(content="已切换到多节点排查。", tool_calls=[]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="active")

    first = await loop.process_direct("storage 集群出问题了", session_key="cli:cluster")
    second = await loop.process_direct("继续", session_key="cli:cluster")

    assert "确认" in first
    assert "多节点" in second
    session = loop.sessions.get_or_create("cli:cluster")
    assert session.metadata.get("expansion_confirmed") is False
    assert session.metadata.get("pending_target_resolution") is None
    assert session.metadata.get("workflow_paused") is False
    assert session.metadata.get("workflow_last_control_input") == "继续"


@pytest.mark.asyncio
async def test_pending_target_confirmation_still_beats_resume_after_targeting_extraction(tmp_path: Path) -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1", "labels": ["storage", "hci"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["storage", "hci"]},
            ],
            "groups": [{"name": "storage-cluster", "targets": ["node-a", "node-b"]}],
        }
    )
    loop = _make_loop(tmp_path, targeting=targeting)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="先对比 storage 集群。",
                tool_calls=[ToolCallRequest(id="1", name="service_status", arguments={"service": "nginx"})],
            ),
            LLMResponse(content="已切换到多节点排查。", tool_calls=[]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="active")

    first = await loop.process_direct("storage 集群出问题了", session_key="cli:cluster")
    second = await loop.process_direct("继续", session_key="cli:cluster")

    assert "确认" in first
    assert "已继续当前排查" not in second
    assert "多节点" in second


@pytest.mark.asyncio
async def test_pending_target_expansion_continue_clears_paused_workflow_state(tmp_path: Path) -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1", "labels": ["storage", "hci"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["storage", "hci"]},
            ],
            "groups": [{"name": "storage-cluster", "targets": ["node-a", "node-b"]}],
        }
    )
    loop = _make_loop(tmp_path, targeting=targeting)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="先对比 storage 集群。",
                tool_calls=[ToolCallRequest(id="1", name="service_status", arguments={"service": "nginx"})],
            ),
            LLMResponse(content="已切换到多节点排查。", tool_calls=[]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="active")

    await loop.process_direct("暂停", session_key="cli:cluster")
    first = await loop.process_direct("storage 集群出问题了", session_key="cli:cluster")
    second = await loop.process_direct("继续", session_key="cli:cluster")

    assert "确认" in first
    assert "多节点" in second
    session = loop.sessions.get_or_create("cli:cluster")
    assert session.metadata.get("workflow_paused") is False
    assert session.metadata.get("workflow_last_control_input") == "继续"


@pytest.mark.asyncio
async def test_process_direct_pause_stores_workflow_paused_state(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(side_effect=AssertionError("provider should not be called"))

    result = await loop.process_direct("暂停", session_key="cli:workflow")

    assert "暂停" in result
    session = loop.sessions.get_or_create("cli:workflow")
    assert session.metadata.get("workflow_paused") is True
    assert session.metadata.get("workflow_last_control_input") == "暂停"


@pytest.mark.asyncio
async def test_process_direct_pause_control_still_works_after_control_extraction(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(side_effect=AssertionError("provider should not be called"))

    result = await loop.process_direct("暂停", session_key="cli:workflow")

    assert "已暂停当前排查" in result


@pytest.mark.asyncio
async def test_process_direct_resume_clears_workflow_paused_state(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(side_effect=AssertionError("provider should not be called"))

    await loop.process_direct("暂停", session_key="cli:workflow")
    result = await loop.process_direct("继续", session_key="cli:workflow")

    assert "继续" in result
    session = loop.sessions.get_or_create("cli:workflow")
    assert session.metadata.get("workflow_paused") is False
    assert session.metadata.get("workflow_last_control_input") == "继续"


@pytest.mark.asyncio
async def test_process_direct_resume_takes_precedence_over_compound_evidence_first_phrase(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(side_effect=AssertionError("provider should not be called"))

    await loop.process_direct("暂停", session_key="cli:workflow")
    result = await loop.process_direct("继续，先证据后判断", session_key="cli:workflow")

    assert "继续" in result
    session = loop.sessions.get_or_create("cli:workflow")
    assert session.metadata.get("workflow_paused") is False
    assert session.metadata.get("workflow_result_mode") is None
    assert session.metadata.get("workflow_result_mode_reason") is None
    assert session.metadata.get("workflow_last_control_input") == "继续，先证据后判断"


@pytest.mark.asyncio
async def test_process_direct_new_command_clears_session_state_including_result_mode(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(content="先看一下日志。", tool_calls=[]),
            AssertionError("provider should not be called for /new"),
        ]
    )
    loop._consolidate_memory = AsyncMock(return_value=True)  # type: ignore[method-assign]

    await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")
    await loop.process_direct("先别急着下结论", session_key="cli:workflow")
    result = await loop.process_direct("/new", session_key="cli:workflow")

    assert result == "New session started."
    reloaded = loop.sessions.get_or_create("cli:workflow")
    assert reloaded.messages == []
    assert reloaded.metadata == {}


@pytest.mark.asyncio
async def test_process_direct_change_focus_stores_bounded_focus_hint(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(side_effect=AssertionError("provider should not be called"))

    result = await loop.process_direct("先只看日志", session_key="cli:workflow")

    assert "日志" in result
    session = loop.sessions.get_or_create("cli:workflow")
    assert session.metadata.get("workflow_focus_hint") == "logs_only"
    assert session.metadata.get("workflow_last_control_input") == "先只看日志"


@pytest.mark.asyncio
async def test_process_direct_narrow_scope_blocks_later_multi_target_expansion(tmp_path: Path) -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1", "labels": ["storage", "hci"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["storage", "hci"]},
            ],
            "groups": [{"name": "storage-cluster", "targets": ["node-a", "node-b"]}],
        }
    )
    loop = _make_loop(tmp_path, targeting=targeting)
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content="done", tool_calls=[]))

    result = await loop.process_direct("不要多节点", session_key="cli:cluster")
    followup = await loop.process_direct("storage 集群出问题了", session_key="cli:cluster")

    assert "单节点" in result
    assert "确认" not in followup

    session = loop.sessions.get_or_create("cli:cluster")
    assert session.metadata.get("workflow_scope_constraints") == {"forbid_multi_target": True}
    assert session.metadata.get("pending_target_resolution") is None


@pytest.mark.asyncio
async def test_narrow_scope_clears_confirmed_multi_target_scope_for_later_turns(tmp_path: Path) -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1", "labels": ["storage", "hci"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["storage", "hci"]},
            ],
            "groups": [{"name": "storage-cluster", "targets": ["node-a", "node-b"]}],
        }
    )
    loop = _make_loop(tmp_path, targeting=targeting)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(content="已切回单节点调查。", tool_calls=[]),
            LLMResponse(content="继续按单节点调查。", tool_calls=[]),
        ]
    )

    await loop.process_direct("storage 集群出问题了", session_key="cli:cluster")
    await loop.process_direct("确认", session_key="cli:cluster")
    result = await loop.process_direct("不要多节点", session_key="cli:cluster")
    followup = await loop.process_direct("继续看 storage 状态", session_key="cli:cluster")

    assert "单节点" in result
    assert "确认" not in followup

    session = loop.sessions.get_or_create("cli:cluster")
    assert session.metadata.get("workflow_scope_constraints") == {"forbid_multi_target": True}
    assert session.metadata.get("expansion_confirmed") is False
    assert session.metadata.get("resolved_target_ids") is None


@pytest.mark.asyncio
async def test_process_direct_non_control_chat_does_not_set_workflow_control_state(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content="done", tool_calls=[]))

    result = await loop.process_direct("我们在讨论产品设计方案，先画一下页面结构。", session_key="cli:workflow")

    assert result
    session = loop.sessions.get_or_create("cli:workflow")
    assert "workflow_paused" not in session.metadata
    assert "workflow_focus_hint" not in session.metadata
    assert "workflow_scope_constraints" not in session.metadata
    assert "workflow_last_control_input" not in session.metadata
    assert "workflow_result_mode" not in session.metadata
    assert "workflow_result_mode_reason" not in session.metadata


@pytest.mark.asyncio
async def test_generic_business_chat_with_overlapping_words_does_not_enable_result_mode(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content="继续讨论服务定价方案。", tool_calls=[]))

    result = await loop.process_direct(
        "先别急着下结论，我们先讨论服务定价策略和连接失败补偿方案。",
        session_key="cli:workflow",
    )

    assert result == "继续讨论服务定价方案。"
    session = loop.sessions.get_or_create("cli:workflow")
    assert "workflow_result_mode" not in session.metadata
    assert "workflow_result_mode_reason" not in session.metadata
    assert "workflow_last_control_input" not in session.metadata


@pytest.mark.asyncio
async def test_log_product_discussion_does_not_enable_result_mode(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content="继续讨论日志采集产品路线。", tool_calls=[]))

    result = await loop.process_direct(
        "先别急着下结论，我们先讨论日志采集产品路线。",
        session_key="cli:workflow",
    )

    assert result == "继续讨论日志采集产品路线。"
    session = loop.sessions.get_or_create("cli:workflow")
    assert "workflow_result_mode" not in session.metadata
    assert "workflow_result_mode_reason" not in session.metadata
    assert "workflow_last_control_input" not in session.metadata


@pytest.mark.asyncio
async def test_network_product_positioning_discussion_does_not_enable_result_mode(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content="继续讨论网络产品定位。", tool_calls=[]))

    result = await loop.process_direct(
        "先别急着下结论，我们先讨论网络产品定位。",
        session_key="cli:workflow",
    )

    assert result == "继续讨论网络产品定位。"
    session = loop.sessions.get_or_create("cli:workflow")
    assert "workflow_result_mode" not in session.metadata
    assert "workflow_result_mode_reason" not in session.metadata
    assert "workflow_last_control_input" not in session.metadata


@pytest.mark.asyncio
async def test_cluster_product_planning_discussion_does_not_enable_result_mode(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content="继续讨论集群产品规划。", tool_calls=[]))

    result = await loop.process_direct(
        "先别急着下结论，我们先讨论集群产品规划。",
        session_key="cli:workflow",
    )

    assert result == "继续讨论集群产品规划。"
    session = loop.sessions.get_or_create("cli:workflow")
    assert "workflow_result_mode" not in session.metadata
    assert "workflow_result_mode_reason" not in session.metadata
    assert "workflow_last_control_input" not in session.metadata


@pytest.mark.asyncio
async def test_ordinary_non_troubleshooting_chat_does_not_enable_result_mode_after_prior_troubleshooting(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(content="先看一下日志。", tool_calls=[]),
            LLMResponse(content="继续讨论产品方案。", tool_calls=[]),
        ]
    )

    await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")
    result = await loop.process_direct(
        "先别急着下结论，但是这是产品设计讨论，先定一下页面布局。",
        session_key="cli:workflow",
    )

    assert result == "继续讨论产品方案。"
    session = loop.sessions.get_or_create("cli:workflow")
    assert "workflow_result_mode" not in session.metadata
    assert "workflow_result_mode_reason" not in session.metadata
    assert "workflow_last_control_input" not in session.metadata


@pytest.mark.asyncio
async def test_process_direct_evidence_first_requires_troubleshooting_context(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(content="先看一下服务状态。", tool_calls=[]),
            AssertionError("provider should not be called for a troubleshooting control turn"),
        ]
    )

    await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")
    result = await loop.process_direct("先别急着下结论", session_key="cli:workflow")

    assert result == "后续先按证据收口；如果判断还不够稳，我会先列证据和未确认点。"
    session = loop.sessions.get_or_create("cli:workflow")
    assert session.metadata.get("workflow_result_mode") == "evidence_first"
    assert session.metadata.get("workflow_result_mode_reason") == "先别急着下结论"
    assert session.metadata.get("workflow_last_control_input") == "先别急着下结论"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "expected_reason"),
    [
        ("先别急着下结论", "先别急着下结论"),
        ("先别急着下结论，", "先别急着下结论，"),
        ("先给证据再说判断", "先给证据再说判断"),
        ("先别定性", "先别定性"),
        ("先证据后判断", "先证据后判断"),
    ],
)
async def test_process_direct_enables_evidence_first_result_mode(
    tmp_path: Path,
    content: str,
    expected_reason: str,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(content="先看一下日志。", tool_calls=[]),
            AssertionError("provider should not be called for result-mode control"),
        ]
    )

    await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")
    result = await loop.process_direct(content, session_key="cli:workflow")

    assert result == "后续先按证据收口；如果判断还不够稳，我会先列证据和未确认点。"
    session = loop.sessions.get_or_create("cli:workflow")
    assert session.metadata.get("workflow_result_mode") == "evidence_first"
    assert session.metadata.get("workflow_result_mode_reason") == expected_reason
    assert session.metadata.get("workflow_last_control_input") == content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "expected_reply"),
    [
        ("直接说结论", "已解除证据优先收口；后续可直接给出判断。"),
        ("你可以下判断了", "已解除证据优先收口；后续可直接给出判断。"),
        ("直接给判断", "已解除证据优先收口；后续可直接给出判断。"),
    ],
)
async def test_process_direct_disables_evidence_first_result_mode(
    tmp_path: Path,
    content: str,
    expected_reply: str,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(content="先看一下日志。", tool_calls=[]),
            AssertionError("provider should not be called for result-mode control"),
        ]
    )

    await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")
    await loop.process_direct("先别急着下结论", session_key="cli:workflow")
    result = await loop.process_direct(content, session_key="cli:workflow")

    assert result == expected_reply
    session = loop.sessions.get_or_create("cli:workflow")
    assert session.metadata.get("workflow_result_mode") is None
    assert session.metadata.get("workflow_result_mode_reason") is None
    assert session.metadata.get("workflow_last_control_input") == content


@pytest.mark.asyncio
async def test_process_direct_normal_troubleshooting_prompt_leaves_result_mode_unset(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content="done", tool_calls=[]))

    await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")

    session = loop.sessions.get_or_create("cli:workflow")
    assert "workflow_result_mode" not in session.metadata
    assert "workflow_result_mode_reason" not in session.metadata
    assert "workflow_last_control_input" not in session.metadata


@pytest.mark.asyncio
async def test_evidence_first_result_mode_persists_across_followup_turns(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(content="先看日志。", tool_calls=[]),
            LLMResponse(content="继续排查。", tool_calls=[]),
        ]
    )

    await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")
    await loop.process_direct("先别急着下结论", session_key="cli:workflow")
    await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")
    loop.sessions.invalidate("cli:workflow")

    session = loop.sessions.get_or_create("cli:workflow")
    assert session.metadata.get("workflow_result_mode") == "evidence_first"
    assert session.metadata.get("workflow_result_mode_reason") == "先别急着下结论"
    assert session.metadata.get("workflow_last_control_input") == "先别急着下结论"


@pytest.mark.asyncio
async def test_process_direct_combined_investigation_control_beats_result_mode_phrase(
    tmp_path: Path,
) -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1", "labels": ["storage", "hci"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["storage", "hci"]},
            ],
            "groups": [{"name": "storage-cluster", "targets": ["node-a", "node-b"]}],
        }
    )
    loop = _make_loop(tmp_path, targeting=targeting)
    loop.provider.chat = AsyncMock(side_effect=AssertionError("provider should not be called"))

    result = await loop.process_direct("先只看日志，先别急着下结论", session_key="cli:cluster")

    assert "日志" in result
    session = loop.sessions.get_or_create("cli:cluster")
    assert session.metadata.get("workflow_focus_hint") == "logs_only"
    assert session.metadata.get("workflow_result_mode") is None
    assert session.metadata.get("workflow_result_mode_reason") is None


@pytest.mark.asyncio
async def test_process_direct_combined_turn_honors_investigation_control_even_when_result_phrase_is_first(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(side_effect=AssertionError("provider should not be called"))

    result = await loop.process_direct("先别急着下结论，先只看日志", session_key="cli:workflow")

    assert "日志" in result
    session = loop.sessions.get_or_create("cli:workflow")
    assert session.metadata.get("workflow_focus_hint") == "logs_only"
    assert session.metadata.get("workflow_result_mode") is None
    assert session.metadata.get("workflow_result_mode_reason") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "provider_reply"),
    [
        ("inspection:run", "inspection artifact body"),
        ("生成案例摘要", "case artifact body"),
        ("保存案例", "report artifact body"),
    ],
)
async def test_workflow_result_mode_does_not_rewrite_structured_artifact_paths(
    tmp_path: Path,
    content: str,
    provider_reply: str,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content=provider_reply, tool_calls=[]))
    session = loop.sessions.get_or_create("cli:workflow")
    session.metadata["workflow_result_mode"] = "evidence_first"
    session.metadata["workflow_result_mode_reason"] = "先别急着下结论"
    loop.sessions.save(session)

    result = await loop.process_direct(content, session_key="cli:workflow")

    assert result == provider_reply
    reloaded = loop.sessions.get_or_create("cli:workflow")
    assert reloaded.metadata.get("workflow_result_mode") == "evidence_first"


@pytest.mark.asyncio
async def test_workflow_result_mode_does_not_rewrite_timeline_artifact_body(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    body = (
        "# Timeline\n"
        "Incident: storage timeout incident\n"
        "Target: node-a\n"
        "Window: 2026-03-18T10:21:03Z to 2026-03-18T10:28:41Z\n"
        "\n"
        "## Events\n"
        "\n"
        "- Timestamp: 2026-03-18T10:21:03Z\n"
        "  Event: node-a started reporting storage backend timeout\n"
        "  Evidence: /var/log/storage.log:120 `timeout while connecting to backend`\n"
        "  Target: node-a\n"
        "  Source: search_log\n"
        "\n"
        "## Coverage Note\n"
        "\n"
        "Only evidence with explicit timestamps is included in this timeline.\n"
    )
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content=body, tool_calls=[]))
    session = loop.sessions.get_or_create("cli:workflow")
    session.metadata["workflow_result_mode"] = "evidence_first"
    session.metadata["workflow_result_mode_reason"] = "先别急着下结论"
    loop.sessions.save(session)

    result = await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")

    assert result == body.strip()


@pytest.mark.asyncio
async def test_evidence_first_result_shaping_downgrades_strong_conclusion_and_keeps_evidence_first(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(
        return_value=LLMResponse(
            content="已确认事实：日志里连续出现轮转失败；关键证据：node-a 上的 logrotate 报错。根因已确认，就是日志轮转失败。",
            tool_calls=[],
        )
    )
    session = loop.sessions.get_or_create("cli:workflow")
    session.metadata["workflow_result_mode"] = "evidence_first"
    session.metadata["workflow_result_mode_reason"] = "先别急着下结论"
    loop.sessions.save(session)

    result = await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")

    assert result.startswith("已确认事实：")
    assert result.index("已确认事实：") < result.index("当前倾向")
    assert "根因已确认" not in result
    assert "日志轮转失败" in result
    assert "不确定点" in result
    assert "下一步" in result


@pytest.mark.asyncio
async def test_evidence_first_result_still_downgrades_strong_conclusion_after_result_policy_extraction(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(
        return_value=LLMResponse(
            content="已确认事实：日志里持续报错。根因已确认，就是日志轮转失败。",
            tool_calls=[],
        )
    )
    session = loop.sessions.get_or_create("cli:workflow")
    session.metadata["workflow_result_mode"] = "evidence_first"
    session.metadata["workflow_result_mode_reason"] = "先别急着下结论"
    loop.sessions.save(session)

    result = await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")

    assert "当前倾向" in result
    assert "根因已确认" not in result


@pytest.mark.asyncio
async def test_evidence_first_result_shaping_downgrades_conclusion_only_reply(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content="根因已确认，就是日志轮转失败。", tool_calls=[]))
    session = loop.sessions.get_or_create("cli:workflow")
    session.metadata["workflow_result_mode"] = "evidence_first"
    session.metadata["workflow_result_mode_reason"] = "先别急着下结论"
    loop.sessions.save(session)

    result = await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")

    assert "当前倾向" not in result
    assert "根因已确认" not in result
    assert "证据缺口" in result
    assert "不确定点" in result
    assert "下一步" in result


@pytest.mark.asyncio
async def test_evidence_first_result_shaping_adds_minimal_uncertainty_and_next_step_when_missing(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(
        return_value=LLMResponse(
            content="日志里有报错；node-a 的服务状态异常。问题已经定位到 node-a。",
            tool_calls=[],
        )
    )
    session = loop.sessions.get_or_create("cli:workflow")
    session.metadata["workflow_result_mode"] = "evidence_first"
    session.metadata["workflow_result_mode_reason"] = "先给证据再说判断"
    loop.sessions.save(session)

    result = await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")

    assert "当前倾向" in result
    assert "不确定点" in result
    assert "下一步" in result
    assert result.index("日志里有报错") < result.index("当前倾向")


@pytest.mark.asyncio
async def test_evidence_first_result_shaping_omits_tendency_when_evidence_is_weak(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content="只有一条日志报错。可以确定就是服务配置错误。", tool_calls=[]))
    session = loop.sessions.get_or_create("cli:workflow")
    session.metadata["workflow_result_mode"] = "evidence_first"
    session.metadata["workflow_result_mode_reason"] = "先别急着下结论"
    loop.sessions.save(session)

    result = await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")

    assert "当前倾向" not in result
    assert "可以确定就是服务配置错误" not in result
    assert "日志报错" in result
    assert "不确定点" in result
    assert "下一步" in result


@pytest.mark.asyncio
async def test_workflow_result_mode_keeps_investigation_tool_calls_and_only_changes_final_shape(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="先看日志。",
                tool_calls=[ToolCallRequest(id="1", name="read_log_tail", arguments={"path": "/var/log/app.log"})],
            ),
            LLMResponse(content="根因已确认，就是日志轮转失败。", tool_calls=[]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="same readonly evidence")
    session = loop.sessions.get_or_create("cli:workflow")
    session.metadata["workflow_result_mode"] = "evidence_first"
    session.metadata["workflow_result_mode_reason"] = "先别急着下结论"
    loop.sessions.save(session)

    result = await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")

    assert loop.tools.execute.await_count == 1
    assert loop.tools.execute.await_args_list[0].args[0] == "read_log_tail"
    assert loop.tools.execute.await_args_list[0].args[1] == {"path": "/var/log/app.log"}
    assert "已确认事实：" in result
    assert "当前倾向" in result
    assert result.index("已确认事实：") < result.index("当前倾向")


@pytest.mark.asyncio
async def test_workflow_result_mode_does_not_rewrite_structured_artifact_body(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    body = """---\ntype: inspection_report\ncase_id: INC-20260319-001\n---\n# Inspection report\n\n## Evidence\n- [node-a/log:42] logrotate failed\n\n## Conclusion\nPlease review report details.\n"""
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content=body, tool_calls=[]))
    session = loop.sessions.get_or_create("cli:workflow")
    session.metadata["workflow_result_mode"] = "evidence_first"
    session.metadata["workflow_result_mode_reason"] = "先别急着下结论"
    loop.sessions.save(session)

    result = await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")

    assert result == body.strip()


@pytest.mark.asyncio
async def test_workflow_result_mode_does_not_rewrite_plain_markdown_report_body(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    body = "# Inspection report\n\n## Evidence\n- node-a logrotate failed\n\n## Conclusion\nPlease review report details.\n"
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content=body, tool_calls=[]))
    session = loop.sessions.get_or_create("cli:workflow")
    session.metadata["workflow_result_mode"] = "evidence_first"
    session.metadata["workflow_result_mode_reason"] = "先别急着下结论"
    loop.sessions.save(session)

    result = await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")

    assert result == body.strip()


@pytest.mark.asyncio
async def test_evidence_first_markdown_troubleshooting_summary_is_still_shaped(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    body = "# 排查结论\n\n已确认事实：日志里持续报错。\n根因已确认，就是日志轮转失败。"
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content=body, tool_calls=[]))
    session = loop.sessions.get_or_create("cli:workflow")
    session.metadata["workflow_result_mode"] = "evidence_first"
    session.metadata["workflow_result_mode_reason"] = "先别急着下结论"
    loop.sessions.save(session)

    result = await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")

    assert "# 排查结论" in result
    assert "当前倾向" in result
    assert "根因已确认" not in result


@pytest.mark.asyncio
async def test_evidence_first_preserves_original_suffix_after_strong_conclusion(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    content = "已确认事实：日志里连续报错。根因已确认，就是日志轮转失败。下一步：先核对 node-a 的轮转配置。"
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content=content, tool_calls=[]))
    session = loop.sessions.get_or_create("cli:workflow")
    session.metadata["workflow_result_mode"] = "evidence_first"
    session.metadata["workflow_result_mode_reason"] = "先别急着下结论"
    loop.sessions.save(session)

    result = await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")

    assert "下一步：先核对 node-a 的轮转配置。" in result
    assert "当前倾向" in result
    assert "根因已确认" not in result


@pytest.mark.asyncio
async def test_evidence_first_rewrites_multiple_strong_conclusion_phrases(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    content = "已确认事实：日志里持续报错。根因已确认，就是日志轮转失败。可以确定就是 node-a 的配置问题。"
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content=content, tool_calls=[]))
    session = loop.sessions.get_or_create("cli:workflow")
    session.metadata["workflow_result_mode"] = "evidence_first"
    session.metadata["workflow_result_mode_reason"] = "先别急着下结论"
    loop.sessions.save(session)

    result = await loop.process_direct("storage 集群出问题了", session_key="cli:workflow")

    assert "根因已确认" not in result
    assert "可以确定就是" not in result
    assert "当前倾向" in result
    assert result.count("当前倾向") == 1
    assert result.count("现有证据更偏向") == 1


@pytest.mark.asyncio
async def test_workflow_result_mode_does_not_change_unrelated_non_troubleshooting_reply(
    tmp_path: Path,
) -> None:
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content="我们先讨论产品定价方案。", tool_calls=[]))
    session = loop.sessions.get_or_create("cli:workflow")
    session.metadata["workflow_result_mode"] = "evidence_first"
    session.metadata["workflow_result_mode_reason"] = "先别急着下结论"
    loop.sessions.save(session)

    result = await loop.process_direct("先别急着下结论，我们先讨论产品定价方案。", session_key="cli:workflow")

    assert result == "我们先讨论产品定价方案。"


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
    assert session.metadata.get("expansion_confirmed") is False
    assert session.metadata.get("resolved_target_ids") is None
    assert session.metadata.get("pending_target_resolution") is None
    assert session.metadata.get("expansion_skip_reprompt_once") is True

    history = session.get_history()
    user_texts = [m["content"] for m in history if m.get("role") == "user"]
    assert "storage 集群出问题了" in user_texts


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


@pytest.mark.asyncio
async def test_confirmed_multi_target_scope_is_cleared_after_one_turn(tmp_path: Path) -> None:
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

    await loop.process_direct("storage 集群出问题了", session_key="cli:cluster")
    await loop.process_direct("确认", session_key="cli:cluster")

    session = loop.sessions.get_or_create("cli:cluster")
    assert session.metadata.get("expansion_confirmed") is False
    assert session.metadata.get("resolved_target_ids") is None


@pytest.mark.asyncio
async def test_confirmed_followup_with_storage_keyword_does_not_re_prompt_confirmation(tmp_path: Path) -> None:
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
        side_effect=[
            LLMResponse(content="done-1", tool_calls=[]),
            LLMResponse(content="done-2", tool_calls=[]),
        ]
    )

    await loop.process_direct("storage 集群出问题了", session_key="cli:cluster")
    confirmed = await loop.process_direct("确认", session_key="cli:cluster")
    followup = await loop.process_direct("继续看 storage 状态", session_key="cli:cluster")

    assert "确认" not in confirmed
    assert "确认" not in followup
    assert followup == "done-2"


@pytest.mark.asyncio
async def test_process_direct_emits_multi_target_execution_progress(tmp_path: Path) -> None:
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
        side_effect=[
            LLMResponse(
                content="准备检查服务状态。",
                tool_calls=[ToolCallRequest(id="1", name="service_status", arguments={"service": "nginx"})],
            ),
            LLMResponse(content="done", tool_calls=[]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="active")
    progress: list[str] = []

    await loop.process_direct("storage 集群出问题了", session_key="cli:cluster")
    await loop.process_direct(
        "确认",
        session_key="cli:cluster",
        on_progress=AsyncMock(side_effect=lambda content, **_: progress.append(content)),
    )

    assert any("多节点" in item and "2 个目标" in item for item in progress)


@pytest.mark.asyncio
async def test_process_direct_emits_multi_target_reason_and_summary(tmp_path: Path) -> None:
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
        side_effect=[
            LLMResponse(
                content="先对比服务状态。",
                tool_calls=[ToolCallRequest(id="1", name="service_status", arguments={"service": "nginx"})],
            ),
            LLMResponse(content="done", tool_calls=[]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="active")
    progress: list[str] = []

    await loop.process_direct("storage 集群出问题了", session_key="cli:cluster")
    await loop.process_direct(
        "确认",
        session_key="cli:cluster",
        on_progress=AsyncMock(side_effect=lambda content, **_: progress.append(content)),
    )

    assert any("所以先在多节点间对比" in item for item in progress)
    assert any("刚才先检查了多节点服务状态" in item for item in progress)


@pytest.mark.asyncio
async def test_process_direct_emits_multi_target_heartbeat_progress(tmp_path: Path) -> None:
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
    loop._PROGRESS_HEARTBEAT_INITIAL_S = 0.01
    loop._PROGRESS_HEARTBEAT_INTERVAL_S = 0.01
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="先对比服务状态。",
                tool_calls=[ToolCallRequest(id="1", name="service_status", arguments={"service": "nginx"})],
            ),
            LLMResponse(content="done", tool_calls=[]),
        ]
    )

    async def _slow_execute(*_args, **_kwargs) -> str:
        await asyncio.sleep(0.03)
        return "active"

    loop.tools.execute = AsyncMock(side_effect=_slow_execute)
    progress: list[str] = []

    await loop.process_direct("storage 集群出问题了", session_key="cli:cluster")
    await loop.process_direct(
        "确认",
        session_key="cli:cluster",
        on_progress=AsyncMock(side_effect=lambda content, **_: progress.append(content)),
    )

    assert any("已完成 1/2" in item or "仍在多节点检查中" in item for item in progress)
