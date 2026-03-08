import json
from pathlib import Path

import pytest

from nanobot.agent.tools.diagnostics import (
    DiagnoseLogReadTool,
    DiagnoseLogSearchTool,
    DiagnoseSystemStatusTool,
)


@pytest.mark.asyncio
async def test_diagnose_log_read_denies_outside_allowed_paths(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    log_file.write_text("line1\nline2\n", encoding="utf-8")

    tool = DiagnoseLogReadTool(allowed_paths=[str(tmp_path / "allowed")])
    result = await tool.execute(path=str(log_file))

    assert "outside allowed paths" in result


@pytest.mark.asyncio
async def test_diagnose_log_read_tail_and_head(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    log_file.write_text("1\n2\n3\n4\n", encoding="utf-8")

    tool = DiagnoseLogReadTool(workspace=tmp_path, allowed_paths=[str(tmp_path)], max_read_lines=10)
    tail = await tool.execute(path=str(log_file), lines=2, mode="tail")
    head = await tool.execute(path=str(log_file), lines=2, mode="head")

    assert "3" in tail and "4" in tail
    assert "1" in head and "2" in head

    audit_file = tmp_path / "audit" / "commands.jsonl"
    assert audit_file.exists()
    payload = json.loads(audit_file.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["source"] == "diagnose_log_read"


@pytest.mark.asyncio
async def test_diagnose_log_search_limits_results(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    log_file.write_text("error one\nok\nerror two\nerror three\n", encoding="utf-8")

    tool = DiagnoseLogSearchTool(workspace=tmp_path, allowed_paths=[str(tmp_path)], max_search_hits=2)
    result = await tool.execute(path=str(log_file), pattern="error", max_hits=10)

    assert "Found 2 match(es)" in result
    assert "error three" not in result


@pytest.mark.asyncio
async def test_diagnose_log_search_invalid_regex(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    log_file.write_text("error one\n", encoding="utf-8")

    tool = DiagnoseLogSearchTool(workspace=tmp_path, allowed_paths=[str(tmp_path)])
    result = await tool.execute(path=str(log_file), pattern="(")

    assert result.startswith("Error: Invalid regex pattern:")

    audit_file = tmp_path / "audit" / "commands.jsonl"
    assert audit_file.exists()


@pytest.mark.asyncio
async def test_diagnose_system_status_rejects_unknown_scope(tmp_path: Path) -> None:
    tool = DiagnoseSystemStatusTool(workspace=tmp_path)
    result = await tool.execute(scope="unknown")

    assert "Unsupported scope" in result


@pytest.mark.asyncio
async def test_diagnose_log_read_remote_uses_ssh_bridge(tmp_path: Path) -> None:
    tool = DiagnoseLogReadTool(
        workspace=tmp_path,
        allowed_paths=["/sf/log/today"],
        allow_remote_ssh=True,
        allowed_ssh_hosts=["10.10.10.8"],
    )

    async def fake_run_cmd(args: list[str], **kwargs: object) -> str:
        assert args == ["tail", "-n", "2", "/sf/log/today/update.log"]
        assert kwargs["target_host"] == "10.10.10.8"
        assert kwargs["target_user"] == "root"
        return "line 1\nline 2"

    tool._run_cmd = fake_run_cmd  # type: ignore[method-assign]
    result = await tool.execute(
        path="/sf/log/today/update.log",
        lines=2,
        mode="tail",
        target_host="10.10.10.8",
        target_user="root",
    )

    assert "10.10.10.8" in result
    assert "line 1" in result


@pytest.mark.asyncio
async def test_diagnose_log_search_remote_blocks_unapproved_host(tmp_path: Path) -> None:
    tool = DiagnoseLogSearchTool(
        workspace=tmp_path,
        allowed_paths=["/sf/log/today"],
        allow_remote_ssh=True,
        allowed_ssh_hosts=["10.10.10.8"],
    )

    result = await tool.execute(
        path="/sf/log/today/update.log",
        pattern="error",
        target_host="10.10.10.9",
    )

    assert "approved host list" in result


@pytest.mark.asyncio
async def test_diagnose_system_status_remote_uses_ssh_bridge(tmp_path: Path) -> None:
    tool = DiagnoseSystemStatusTool(
        workspace=tmp_path,
        allow_remote_ssh=True,
        allowed_ssh_hosts=["10.10.10.8"],
    )

    calls: list[tuple[list[str], dict[str, object]]] = []

    async def fake_run_cmd(args: list[str], **kwargs: object) -> str:
        calls.append((args, kwargs))
        return "ok"

    tool._run_cmd = fake_run_cmd  # type: ignore[method-assign]
    result = await tool.execute(scope="general", target_host="10.10.10.8", target_user="root")

    assert "remote: 10.10.10.8" in result
    assert len(calls) == 2
    assert calls[0][1]["target_host"] == "10.10.10.8"
