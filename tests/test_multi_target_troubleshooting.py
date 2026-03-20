from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.agent.multi_target import aggregate_multi_target_results, execute_multi_target_tool
from nanobot.agent.timeline import TimelineArtifact, format_timeline_artifact
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

    assert "Shared Findings" in summary
    assert "node-a, node-b" in summary
    assert "active" in summary
    assert "Failed Targets" in summary
    assert "node-c: timeout" in summary


@pytest.mark.parametrize(
    ("tool_name", "results"),
    [
        (
            "search_log",
            [
                {
                    "target_id": "node-a",
                    "target_host": "root@10.0.0.1",
                    "status": "ok",
                    "content": (
                        "[target=root@10.0.0.1] Found matches in /sf/log/app.log:\n"
                        "12: 2026-03-18 10:21:03 timeout while connecting to storage backend"
                    ),
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-b",
                    "target_host": "root@10.0.0.2",
                    "status": "ok",
                    "content": (
                        "[target=root@10.0.0.2] Found matches in /sf/log/app.log:\n"
                        "18: 2026-03-18 10:21:05 timeout while connecting to storage backend"
                    ),
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-c",
                    "target_host": "root@10.0.0.3",
                    "status": "error",
                    "content": "",
                    "error": "ssh timeout",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
            ],
        ),
        (
            "service_status",
            [
                {
                    "target_id": "node-a",
                    "target_host": "root@10.0.0.1",
                    "status": "ok",
                    "content": "[target=root@10.0.0.1] service_status(nginx)\nactive (running)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-b",
                    "target_host": "root@10.0.0.2",
                    "status": "ok",
                    "content": "[target=root@10.0.0.2] service_status(nginx)\ninactive (dead)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
            ],
        ),
    ],
)
def test_aggregate_multi_target_results_renders_stable_summary_for_log_and_state_tools(
    tool_name: str,
    results: list[dict[str, object]],
) -> None:
    summary = str(aggregate_multi_target_results(tool_name=tool_name, results=results))

    assert summary.startswith(f"## Multi-Target Summary: {tool_name}")
    assert "Targets:" in summary
    if tool_name == "search_log":
        assert "### Shared Findings" in summary
        assert "### Failed Targets" in summary
    else:
        assert "### Local Findings" in summary
    assert "## Per-Target Results" not in summary


def test_aggregate_multi_target_results_omits_empty_sections_when_all_targets_share_one_state() -> None:
    summary = str(
        aggregate_multi_target_results(
            tool_name="service_status",
            results=[
                {
                    "target_id": "node-a",
                    "target_host": "root@10.0.0.1",
                    "status": "ok",
                    "content": "[target=root@10.0.0.1] service_status(nginx)\nactive (running)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-b",
                    "target_host": "root@10.0.0.2",
                    "status": "ok",
                    "content": "[target=root@10.0.0.2] service_status(nginx)\nactive (running)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
            ],
        )
    )

    assert "### Shared Findings" in summary
    assert "### Local Findings" not in summary
    assert "### Failed Targets" not in summary


def test_timeline_summary_from_search_log_shared_plus_local_events() -> None:
    aggregation = aggregate_multi_target_results(
        tool_name="search_log",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.2] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-c",
                "target_host": "root@10.0.0.3",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.3] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:22:11 permission denied writing to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 22, 30),
            },
        ],
    )

    summary = aggregation.build_cross_target_timeline_summary()

    assert summary == (
        "时间线补充：最早在 10:21:03 由 node-a,node-b 出现同类超时；"
        "10:22:11 起 node-c 出现本地 permission denied。"
    )


def test_timeline_summary_from_read_log_tail_near_shared_first_cluster() -> None:
    aggregation = aggregate_multi_target_results(
        tool_name="read_log_tail",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] tail 1 lines from /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.2] tail 1 lines from /sf/log/app.log:\n"
                    "2026-03-20 10:21:04 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
        ],
    )

    summary = aggregation.build_cross_target_timeline_summary()

    assert summary == (
        "时间线补充：最早在 10:21:03 由 node-a 出现超时，"
        "node-b 随后近同时出现同类异常。"
    )


def test_timeline_summary_uses_first_cross_target_cluster_when_local_event_appears_earlier() -> None:
    aggregation = aggregate_multi_target_results(
        tool_name="search_log",
        results=[
            {
                "target_id": "node-c",
                "target_host": "root@10.0.0.3",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.3] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:20:01 cache warmup completed"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 20, 10),
            },
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.2] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
        ],
    )

    summary = aggregation.build_cross_target_timeline_summary()

    assert summary == (
        "时间线补充：最早在 10:21:03 由 node-a,node-b 出现同类超时。"
    )


def test_timeline_summary_uses_later_local_event_after_first_cross_target_cluster() -> None:
    aggregation = aggregate_multi_target_results(
        tool_name="read_log_tail",
        results=[
            {
                "target_id": "node-c",
                "target_host": "root@10.0.0.3",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.3] tail 1 lines from /sf/log/app.log:\n"
                    "2026-03-20 10:20:01 cache warmup completed"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 20, 10),
            },
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] tail 1 lines from /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.2] tail 1 lines from /sf/log/app.log:\n"
                    "2026-03-20 10:21:04 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-d",
                "target_host": "root@10.0.0.4",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.4] tail 1 lines from /sf/log/app.log:\n"
                    "2026-03-20 10:23:11 permission denied writing to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 23, 30),
            },
            {
                "target_id": "node-e",
                "target_host": "root@10.0.0.5",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.5] tail 1 lines from /sf/log/app.log:\n"
                    "2026-03-20 10:24:12 connection refused by backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 24, 30),
            },
        ],
    )

    summary = aggregation.build_cross_target_timeline_summary()

    assert summary == (
        "时间线补充：最早在 10:21:03 由 node-a 出现超时，"
        "node-b 随后近同时出现同类异常；10:23:11 起 node-d 出现本地 permission denied。"
    )


def test_timeline_summary_returns_none_when_no_timestamped_log_events_exist() -> None:
    aggregation = aggregate_multi_target_results(
        tool_name="search_log",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] Found 2 match(es) in /sf/log/app.log:\n"
                    "timeout while connecting to storage backend\n"
                    "worker exited unexpectedly"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.2] Found 1 match(es) in /sf/log/app.log:\n"
                    "permission denied writing to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
        ],
    )

    assert aggregation.build_cross_target_timeline_summary() is None


def test_timeline_summary_returns_none_for_non_log_tools() -> None:
    aggregation = aggregate_multi_target_results(
        tool_name="service_status",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": "[target=root@10.0.0.1] service_status(nginx)\nactive (running)",
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": "[target=root@10.0.0.2] service_status(nginx)\ninactive (dead)",
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
        ],
    )

    assert aggregation.build_cross_target_timeline_summary() is None


def test_timeline_summary_returns_none_when_timeline_body_is_effectively_single_target() -> None:
    aggregation = aggregate_multi_target_results(
        tool_name="search_log",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
        ],
    )

    assert aggregation.build_cross_target_timeline_summary() is None


@pytest.mark.asyncio
async def test_execute_multi_target_tool_keeps_grouped_summary_and_raw_per_target_results() -> None:
    async def _exec(name: str, params: dict[str, object]) -> str:
        return (
            f"[target={params['target']}] {name}(nginx)\n"
            f"{'active (running)' if params['target'] == 'root@10.0.0.1' else 'inactive (dead)'}"
        )

    rendered = await execute_multi_target_tool(
        tool_name="service_status",
        arguments={"service": "nginx"},
        resolved_targets=[
            {"id": "node-a", "target": "root@10.0.0.1"},
            {"id": "node-b", "target": "root@10.0.0.2"},
        ],
        execute_tool=_exec,
    )

    assert rendered.startswith("## Multi-Target Summary: service_status")
    assert "Targets:" in rendered
    assert "## Per-Target Results" in rendered
    assert "[multi-target][node-a -> root@10.0.0.1]" in rendered
    assert "[multi-target][node-b -> root@10.0.0.2]" in rendered


@pytest.mark.parametrize(
    ("tool_name", "results"),
    [
        (
            "search_log",
            [
                {
                    "target_id": "node-b",
                    "target_host": "root@10.0.0.2",
                    "status": "ok",
                    "content": (
                        "[target=root@10.0.0.2] Found matches in /sf/log/app.log:\n"
                        "18: 2026-03-18 10:21:03 timeout while connecting to storage backend"
                    ),
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-a",
                    "target_host": "root@10.0.0.1",
                    "status": "ok",
                    "content": (
                        "[target=root@10.0.0.1] Found matches in /sf/log/app.log:\n"
                        "12: 2026-03-18 10:21:03 timeout while connecting to storage backend"
                    ),
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-c",
                    "target_host": "root@10.0.0.3",
                    "status": "ok",
                    "content": (
                        "[target=root@10.0.0.3] Found matches in /sf/log/app.log:\n"
                        "21: 2026-03-18 10:22:11 permission denied writing to storage backend"
                    ),
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-d",
                    "target_host": "root@10.0.0.4",
                    "status": "error",
                    "content": "",
                    "error": "ssh timeout",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
            ],
        ),
        (
            "read_log_tail",
            [
                {
                    "target_id": "node-b",
                    "target_host": "root@10.0.0.2",
                    "status": "ok",
                    "content": (
                        "[target=root@10.0.0.2] tail 1 lines from /sf/log/app.log:\n"
                        "2026-03-18 10:21:03 timeout while connecting to storage backend"
                    ),
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-a",
                    "target_host": "root@10.0.0.1",
                    "status": "ok",
                    "content": (
                        "[target=root@10.0.0.1] tail 1 lines from /sf/log/app.log:\n"
                        "2026-03-18 10:21:03 timeout while connecting to storage backend"
                    ),
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-c",
                    "target_host": "root@10.0.0.3",
                    "status": "ok",
                    "content": (
                        "[target=root@10.0.0.3] tail 1 lines from /sf/log/app.log:\n"
                        "2026-03-18 10:22:11 permission denied writing to storage backend"
                    ),
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-d",
                    "target_host": "root@10.0.0.4",
                    "status": "error",
                    "content": "",
                    "error": "ssh timeout",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
            ],
        ),
    ],
)
def test_aggregate_multi_target_results_returns_structured_log_aggregation_contract(
    tool_name: str,
    results: list[dict[str, object]],
) -> None:
    aggregation = aggregate_multi_target_results(tool_name=tool_name, results=results)

    assert aggregation.tool_name == tool_name
    assert aggregation.targets_total == 4
    assert aggregation.ok_targets == ["node-b", "node-a", "node-c"]
    assert [entry.target_id for entry in aggregation.per_target_results] == [
        "node-b",
        "node-a",
        "node-c",
        "node-d",
    ]

    assert len(aggregation.shared_findings) == 1
    shared = aggregation.shared_findings[0]
    assert shared.signature
    assert shared.target_ids == ["node-b", "node-a"]
    assert shared.target_hosts == ["root@10.0.0.2", "root@10.0.0.1"]
    assert shared.count == 2
    assert shared.kind == "shared"
    assert "timeout while connecting to storage backend" in shared.sample_evidence

    assert len(aggregation.local_findings) == 1
    local = aggregation.local_findings[0]
    assert local.signature
    assert local.target_ids == ["node-c"]
    assert local.target_hosts == ["root@10.0.0.3"]
    assert local.count == 1
    assert local.kind == "local"
    assert "permission denied writing to storage backend" in local.sample_evidence

    assert len(aggregation.failed_targets) == 1
    failed = aggregation.failed_targets[0]
    assert failed.target_id == "node-d"
    assert failed.target_host == "root@10.0.0.4"
    assert failed.status == "error"
    assert failed.error == "ssh timeout"
    assert "node-d" not in aggregation.shared_findings[0].target_ids
    assert "node-d" not in aggregation.local_findings[0].target_ids


def test_cross_target_timeline_artifact_output_from_search_log_shared_plus_local_evidence() -> None:
    aggregation = aggregate_multi_target_results(
        tool_name="search_log",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.2] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-c",
                "target_host": "root@10.0.0.3",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.3] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:22:11 permission denied writing to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 22, 30),
            },
        ],
    )

    artifact = aggregation.build_cross_target_timeline_artifact(
        incident="storage timeout incident",
        target_scope="node-a,node-b,node-c",
    )

    assert isinstance(artifact, TimelineArtifact)
    assert artifact.target == "node-a,node-b,node-c"
    assert [event.scope for event in artifact.events] == ["shared", "local"]
    assert [event.target for event in artifact.events] == ["node-a,node-b", "node-c"]
    markdown = format_timeline_artifact(artifact)
    assert markdown.startswith("# Timeline")
    assert "## Events" in markdown
    assert "timeout while connecting to storage backend" in markdown
    assert "permission denied writing to storage backend" in markdown


def test_cross_target_timeline_artifact_output_from_read_log_tail_near_shared_evidence() -> None:
    aggregation = aggregate_multi_target_results(
        tool_name="read_log_tail",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] tail 1 lines from /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.2] tail 1 lines from /sf/log/app.log:\n"
                    "2026-03-20 10:21:04 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
        ],
    )

    artifact = aggregation.build_cross_target_timeline_artifact(
        target_scope="node-a,node-b",
    )

    assert isinstance(artifact, TimelineArtifact)
    assert [event.scope for event in artifact.events] == ["near_shared"]
    assert [event.target for event in artifact.events] == ["node-a,node-b"]
    markdown = format_timeline_artifact(artifact)
    assert "## Coverage Note" in markdown
    assert "## Events" in markdown
    assert "timeout while connecting to storage backend" in markdown


@pytest.mark.parametrize(
    "results",
    [
        [
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] tail 1 lines from /sf/log/app.log:\n"
                    "timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            }
        ],
        [
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "error",
                "content": "",
                "error": "ssh timeout",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            }
        ],
    ],
)
def test_cross_target_timeline_artifact_output_returns_none_when_no_timestamped_log_events_exist(
    results: list[dict[str, object]],
) -> None:
    aggregation = aggregate_multi_target_results(tool_name="read_log_tail", results=results)

    artifact = aggregation.build_cross_target_timeline_artifact(target_scope="node-a")

    assert artifact is None


@pytest.mark.parametrize(
    ("tool_name", "results"),
    [
        (
            "service_status",
            [
                {
                    "target_id": "node-a",
                    "target_host": "root@10.0.0.1",
                    "status": "ok",
                    "content": "[target=root@10.0.0.1] service_status(nginx)\nactive (running)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 20, 10, 21, 30),
                },
                {
                    "target_id": "node-b",
                    "target_host": "root@10.0.0.2",
                    "status": "ok",
                    "content": "[target=root@10.0.0.2] service_status(nginx)\ninactive (dead)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 20, 10, 21, 30),
                },
            ],
        ),
        (
            "process_snapshot",
            [
                {
                    "target_id": "node-a",
                    "target_host": "root@10.0.0.1",
                    "status": "ok",
                    "content": "[target=root@10.0.0.1] process_snapshot(nginx)\nactive (running)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 20, 10, 21, 30),
                },
                {
                    "target_id": "node-b",
                    "target_host": "root@10.0.0.2",
                    "status": "ok",
                    "content": "[target=root@10.0.0.2] process_snapshot(nginx)\ninactive (dead)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 20, 10, 21, 30),
                },
            ],
        ),
    ],
)
def test_cross_target_timeline_artifact_output_keeps_state_tools_out_of_timeline_path(
    tool_name: str,
    results: list[dict[str, object]],
) -> None:
    aggregation = aggregate_multi_target_results(tool_name=tool_name, results=results)

    artifact = aggregation.build_cross_target_timeline_artifact(target_scope="node-a,node-b")

    assert artifact is None


@pytest.mark.parametrize(
    ("tool_name", "results"),
    [
        (
            "service_status",
            [
                {
                    "target_id": "node-c",
                    "target_host": "root@10.0.0.3",
                    "status": "ok",
                    "content": "[target=root@10.0.0.3] service_status(nginx)\nactive (running)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-a",
                    "target_host": "root@10.0.0.1",
                    "status": "ok",
                    "content": "[target=root@10.0.0.1] service_status(nginx)\nactive (running)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-b",
                    "target_host": "root@10.0.0.2",
                    "status": "ok",
                    "content": "[target=root@10.0.0.2] service_status(nginx)\ninactive (dead)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
            ],
        ),
        (
            "process_snapshot",
            [
                {
                    "target_id": "node-c",
                    "target_host": "root@10.0.0.3",
                    "status": "ok",
                    "content": "[target=root@10.0.0.3] process_snapshot(nginx)\nactive (running)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-a",
                    "target_host": "root@10.0.0.1",
                    "status": "ok",
                    "content": "[target=root@10.0.0.1] process_snapshot(nginx)\nactive (running)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-b",
                    "target_host": "root@10.0.0.2",
                    "status": "ok",
                    "content": "[target=root@10.0.0.2] process_snapshot(nginx)\ninactive (dead)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
            ],
        ),
    ],
)
def test_aggregate_multi_target_results_returns_structured_state_aggregation_contract(
    tool_name: str,
    results: list[dict[str, object]],
) -> None:
    aggregation = aggregate_multi_target_results(tool_name=tool_name, results=results)

    assert aggregation.tool_name == tool_name
    assert aggregation.targets_total == 3
    assert aggregation.ok_targets == ["node-c", "node-a", "node-b"]
    assert aggregation.failed_targets == []
    assert [entry.target_id for entry in aggregation.per_target_results] == [
        "node-c",
        "node-a",
        "node-b",
    ]
    assert [entry.target_host for entry in aggregation.per_target_results] == [
        "root@10.0.0.3",
        "root@10.0.0.1",
        "root@10.0.0.2",
    ]
    assert [entry.status for entry in aggregation.per_target_results] == ["ok", "ok", "ok"]
    assert [entry.content for entry in aggregation.per_target_results] == [
        "[target=root@10.0.0.3] "
        + ("service_status(nginx)\nactive (running)" if tool_name == "service_status" else "process_snapshot(nginx)\nactive (running)"),
        "[target=root@10.0.0.1] "
        + ("service_status(nginx)\nactive (running)" if tool_name == "service_status" else "process_snapshot(nginx)\nactive (running)"),
        "[target=root@10.0.0.2] "
        + ("service_status(nginx)\ninactive (dead)" if tool_name == "service_status" else "process_snapshot(nginx)\ninactive (dead)"),
    ]
    assert all(entry.error == "" for entry in aggregation.per_target_results)
    assert all(entry.observed_at == datetime(2026, 3, 18, 10, 30, 0) for entry in aggregation.per_target_results)

    assert len(aggregation.shared_findings) == 1
    shared = aggregation.shared_findings[0]
    assert shared.signature
    assert shared.target_ids == ["node-c", "node-a"]
    assert shared.target_hosts == ["root@10.0.0.3", "root@10.0.0.1"]
    assert shared.count == 2
    assert shared.kind == "shared"
    assert "active (running)" in shared.sample_evidence

    assert len(aggregation.local_findings) == 1
    local = aggregation.local_findings[0]
    assert local.signature
    assert local.target_ids == ["node-b"]
    assert local.target_hosts == ["root@10.0.0.2"]
    assert local.count == 1
    assert local.kind == "local"
    assert "inactive (dead)" in local.sample_evidence


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


def test_aggregate_multi_target_results_groups_search_log_matches_as_common_despite_line_number_differences() -> None:
    summary = aggregate_multi_target_results(
        tool_name="search_log",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] Found matches in /sf/log/app.log:\n"
                    "12: 2026-03-18 10:21:03 timeout while connecting to storage backend"
                ),
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.2] Found matches in /sf/log/app.log:\n"
                    "98: 2026-03-18 10:21:05 timeout while connecting to storage backend"
                ),
            },
        ],
    )

    assert "Shared Findings" in summary
    assert "node-a, node-b" in summary


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
    assert "Shared Findings" in summary


def test_aggregate_multi_target_results_does_not_treat_find_logs_as_timeline_input() -> None:
    summary = aggregate_multi_target_results(
        tool_name="find_logs",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] find_logs('upgrade') returned 1 result(s):\n"
                    "/sf/log/today/upgrade-worker.log"
                ),
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.2] find_logs('upgrade') returned 1 result(s):\n"
                    "/sf/log/today/upgrade-worker.log"
                ),
            },
        ],
    )

    assert "Timeline" not in summary
    assert "No Timestamp Evidence" not in summary
    assert "Candidate Root Cause" not in summary


def test_aggregate_multi_target_results_includes_candidate_root_cause_when_supported() -> None:
    summary = aggregate_multi_target_results(
        tool_name="search_log",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] Found matches in /sf/log/app.log:\n"
                    "12: 2026-03-18 10:21:03 timeout while connecting to storage backend"
                ),
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.2] Found matches in /sf/log/app.log:\n"
                    "18: 2026-03-18 10:21:05 timeout while connecting to storage backend"
                ),
            },
        ],
    )

    assert "Candidate Root Cause" in summary
    assert "跨节点共享连接/超时异常" in summary
    assert "Supporting Evidence" in summary


def test_aggregate_multi_target_results_skips_candidate_root_cause_when_evidence_is_weak() -> None:
    summary = aggregate_multi_target_results(
        tool_name="read_log_tail",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] tail 1 lines from /sf/log/app.log:\n"
                    "minor issue observed"
                ),
            },
        ],
    )

    assert "Candidate Root Cause" not in summary


def test_aggregate_multi_target_results_candidate_root_cause_uses_raw_log_snippets() -> None:
    summary = aggregate_multi_target_results(
        tool_name="search_log",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] Found matches in /sf/log/app.log:\n"
                    "12: 2026-03-18 10:21:03 dependency unreachable while connecting to storage backend"
                ),
            },
        ],
    )

    assert "Candidate Root Cause" in summary
    assert "dependency unreachable while connecting to storage backend" in summary


@pytest.mark.asyncio
async def test_execute_multi_target_tool_renders_log_formatter_summary_and_per_target_results() -> None:
    resolved_targets = [
        {"id": "node-b", "target": "root@10.0.0.2"},
        {"id": "node-a", "target": "root@10.0.0.1"},
        {"id": "node-c", "target": "root@10.0.0.3"},
        {"id": "node-d", "target": "root@10.0.0.4"},
    ]

    async def _execute(tool_name: str, params: dict[str, str]) -> str:
        target = params["target"]
        if target == "root@10.0.0.4":
            return "Error: ssh timeout"
        if target == "root@10.0.0.3":
            return (
                "[target=root@10.0.0.3] Found matches in /sf/log/app.log:\n"
                "21: 2026-03-18 10:22:11 permission denied writing to storage backend"
            )
        return (
            f"[target={target}] Found matches in /sf/log/app.log:\n"
            "18: 2026-03-18 10:21:03 timeout while connecting to storage backend"
        )

    output = await execute_multi_target_tool(
        tool_name="search_log",
        arguments={"query": "storage backend"},
        resolved_targets=resolved_targets,
        execute_tool=_execute,
    )

    assert output.startswith("## Multi-Target Summary: search_log")
    assert "Targets: 4 total, 3 ok, 1 failed" in output
    assert "### Shared Findings" in output
    assert "### Local Findings" in output
    assert "### Failed Targets" in output
    assert "## Per-Target Results" in output
    assert "[multi-target][node-d -> root@10.0.0.4]\nError: ssh timeout" in output


def test_aggregate_multi_target_results_renders_state_formatter_summary_without_shared_section_when_all_results_differ(
    ) -> None:
    summary = str(
        aggregate_multi_target_results(
            tool_name="service_status",
            results=[
                {
                    "target_id": "node-c",
                    "target_host": "root@10.0.0.3",
                    "status": "ok",
                    "content": "[target=root@10.0.0.3] service_status(nginx)\nactive (running)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-a",
                    "target_host": "root@10.0.0.1",
                    "status": "ok",
                    "content": "[target=root@10.0.0.1] service_status(nginx)\nreloading (start pending)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-b",
                    "target_host": "root@10.0.0.2",
                    "status": "ok",
                    "content": "[target=root@10.0.0.2] service_status(nginx)\ninactive (dead)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
            ],
        )
    )

    assert summary.startswith("## Multi-Target Summary: service_status")
    assert "Targets: 3 total, 3 ok, 0 failed" in summary
    assert "### Shared Findings" not in summary
    assert "### Local Findings" in summary
    assert "### Failed Targets" not in summary


def test_aggregate_multi_target_results_renders_state_formatter_summary_without_local_or_failed_sections_when_all_results_match(
    ) -> None:
    summary = str(
        aggregate_multi_target_results(
            tool_name="process_snapshot",
            results=[
                {
                    "target_id": "node-b",
                    "target_host": "root@10.0.0.2",
                    "status": "ok",
                    "content": "[target=root@10.0.0.2] process_snapshot(nginx)\nactive (running)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
                {
                    "target_id": "node-a",
                    "target_host": "root@10.0.0.1",
                    "status": "ok",
                    "content": "[target=root@10.0.0.1] process_snapshot(nginx)\nactive (running)",
                    "error": "",
                    "observed_at": datetime(2026, 3, 18, 10, 30, 0),
                },
            ],
        )
    )

    assert summary.startswith("## Multi-Target Summary: process_snapshot")
    assert "Targets: 2 total, 2 ok, 0 failed" in summary
    assert "### Shared Findings" in summary
    assert "### Local Findings" not in summary
    assert "### Failed Targets" not in summary
