import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.agent.tools.troubleshooting import (
    DiskSnapshotTool,
    FindLogsTool,
    FindRecentFilesTool,
    JournalTailTool,
    NetworkSnapshotTool,
    ProcessSnapshotTool,
    ReadLogTailTool,
    SearchLogTool,
    ServiceStatusTool,
    _build_target_runner,
)
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


@pytest.mark.asyncio
async def test_find_logs_returns_bounded_matches(tmp_path) -> None:
    tool = FindLogsTool(allowed_log_roots=[str(tmp_path)])
    (tmp_path / "today").mkdir()
    (tmp_path / "today" / "upgrade-server.log").write_text("ok\n", encoding="utf-8")

    result = await tool.execute(keyword="upgrade", target="local")

    assert "upgrade-server.log" in result


@pytest.mark.asyncio
async def test_read_log_tail_supports_remote_target(monkeypatch) -> None:
    tool = ReadLogTailTool()
    monkeypatch.setattr(
        tool,
        "_run_remote_command",
        AsyncMock(return_value=("tail output", "", 0)),
    )

    result = await tool.execute(path="/sf/log/today/update.log", target="ops@host-a")

    assert "tail output" in result


def test_read_log_tail_accepts_var_log_alias() -> None:
    tool = ReadLogTailTool()
    tool.allowed_log_roots = [Path("/private/var/log")]

    assert tool._is_path_allowed_str("/var/log/system.log") is True


@pytest.mark.asyncio
async def test_search_log_returns_matches(tmp_path) -> None:
    log_file = tmp_path / "app.log"
    log_file.write_text("error one\nok\nerror two\n", encoding="utf-8")
    tool = SearchLogTool(max_hits=10)
    tool.allowed_log_roots = [tmp_path]

    result = await tool.execute(path=str(log_file), pattern="error", target="local")

    assert "error one" in result
    assert "error two" in result


@pytest.mark.asyncio
async def test_service_status_checks_systemd_first(monkeypatch) -> None:
    tool = ServiceStatusTool()
    monkeypatch.setattr(
        tool,
        "_run_remote_command",
        AsyncMock(return_value=("active (running)", "", 0)),
    )

    result = await tool.execute(service="nginx", target="ops@host-a")

    assert "nginx" in result
    assert "ops@host-a" in result


@pytest.mark.asyncio
async def test_process_snapshot_returns_bounded_top_processes(monkeypatch) -> None:
    tool = ProcessSnapshotTool()
    monkeypatch.setattr(
        tool,
        "_run_process",
        AsyncMock(return_value=("proc list", "", 0)),
    )

    result = await tool.execute(target="local")

    assert "proc list" in result


@pytest.mark.asyncio
async def test_journal_tail_accepts_service_and_target(monkeypatch) -> None:
    tool = JournalTailTool()
    monkeypatch.setattr(
        tool,
        "_run_remote_command",
        AsyncMock(return_value=("journal lines", "", 0)),
    )

    result = await tool.execute(service="nginx", target="ops@host-a", lines=100)

    assert "journal lines" in result


@pytest.mark.asyncio
async def test_disk_snapshot_returns_output(monkeypatch) -> None:
    tool = DiskSnapshotTool()
    monkeypatch.setattr(
        tool,
        "_run_process",
        AsyncMock(return_value=("disk", "", 0)),
    )

    result = await tool.execute(target="local")

    assert "disk" in result


@pytest.mark.asyncio
async def test_network_snapshot_returns_bounded_output(monkeypatch) -> None:
    tool = NetworkSnapshotTool()
    monkeypatch.setattr(
        tool,
        "_run_process",
        AsyncMock(return_value=("network", "", 0)),
    )

    result = await tool.execute(target="local")

    assert "network" in result


@pytest.mark.asyncio
async def test_find_recent_files_returns_matches(tmp_path) -> None:
    tool = FindRecentFilesTool(allowed_log_roots=[str(tmp_path)])
    recent = tmp_path / "recent.log"
    stale = tmp_path / "stale.log"
    recent.write_text("ok\n", encoding="utf-8")
    stale.write_text("old\n", encoding="utf-8")
    now = time.time()
    os.utime(stale, (now - 3600 * 5, now - 3600 * 5))

    result = await tool.execute(base_path=str(tmp_path), minutes=60, target="local")

    assert "recent.log" in result
