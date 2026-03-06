import pytest

from nanobot.agent.tools.cases import GetCaseTool, SearchCasesTool
from nanobot.cases.store import CaseStore


@pytest.mark.asyncio
async def test_search_cases_tool_returns_matches(tmp_path) -> None:
    store = CaseStore(workspace=tmp_path, cases_path=str(tmp_path / "notes" / "cases"))
    item = store.write_case(
        title="Storage latency spike",
        trigger="cli",
        source="generated",
        summary="iowait and latency spikes",
        evidence="iostat",
        conclusion="background rebuild",
        suggestion="reschedule rebuild",
        host="node-1",
        service="storage",
        tags=["storage", "latency"],
    )

    tool = SearchCasesTool(workspace=tmp_path, cases_path=str(tmp_path / "notes" / "cases"))
    result = await tool.execute(keyword="latency")
    assert "Found 1 case" in result
    assert item["id"] in result


@pytest.mark.asyncio
async def test_get_case_tool_returns_full_content(tmp_path) -> None:
    store = CaseStore(workspace=tmp_path, cases_path=str(tmp_path / "notes" / "cases"))
    item = store.write_case(
        title="Network drop",
        trigger="cli",
        source="generated",
        summary="drop in vm network path",
        evidence="netstat counters",
        conclusion="queue overflow",
        suggestion="tune nic queue",
    )
    tool = GetCaseTool(workspace=tmp_path, cases_path=str(tmp_path / "notes" / "cases"))
    result = await tool.execute(case_id=item["id"])
    assert "# Problem" in result
    assert "drop in vm network path" in result
