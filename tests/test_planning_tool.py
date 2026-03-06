import pytest

from nanobot.agent.tools.planning import PlanningTool


@pytest.mark.asyncio
async def test_planning_tool_quick_horizon() -> None:
    tool = PlanningTool()
    result = await tool.execute(
        goal="定位 HCI 节点磁盘抖动根因",
        constraints=["readonly", "10min timebox"],
        horizon="quick",
    )
    assert "# Troubleshooting Plan" in result
    assert "Goal: 定位 HCI 节点磁盘抖动根因" in result
    assert "1. Clarify symptoms" in result
    assert "4. Draft mitigation" not in result


def test_planning_tool_schema_requires_goal() -> None:
    tool = PlanningTool()
    errors = tool.validate_params({"horizon": "full"})
    assert any("missing required goal" in e for e in errors)
