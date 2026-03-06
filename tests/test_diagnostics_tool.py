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

    tool = DiagnoseLogReadTool(allowed_paths=[str(tmp_path)], max_read_lines=10)
    tail = await tool.execute(path=str(log_file), lines=2, mode="tail")
    head = await tool.execute(path=str(log_file), lines=2, mode="head")

    assert "3" in tail and "4" in tail
    assert "1" in head and "2" in head


@pytest.mark.asyncio
async def test_diagnose_log_search_limits_results(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    log_file.write_text("error one\nok\nerror two\nerror three\n", encoding="utf-8")

    tool = DiagnoseLogSearchTool(allowed_paths=[str(tmp_path)], max_search_hits=2)
    result = await tool.execute(path=str(log_file), pattern="error", max_hits=10)

    assert "Found 2 match(es)" in result
    assert "error three" not in result


@pytest.mark.asyncio
async def test_diagnose_log_search_invalid_regex(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    log_file.write_text("error one\n", encoding="utf-8")

    tool = DiagnoseLogSearchTool(allowed_paths=[str(tmp_path)])
    result = await tool.execute(path=str(log_file), pattern="(")

    assert result.startswith("Error: Invalid regex pattern:")


@pytest.mark.asyncio
async def test_diagnose_system_status_rejects_unknown_scope() -> None:
    tool = DiagnoseSystemStatusTool()
    result = await tool.execute(scope="unknown")

    assert "Unsupported scope" in result
