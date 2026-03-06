import pytest

from nanobot.agent.tools.cron import CronTool
from nanobot.cron.service import CronService


@pytest.mark.asyncio
async def test_cron_add_inspection_creates_system_event_job(tmp_path) -> None:
    service = CronService(tmp_path / "cron" / "jobs.json")
    tool = CronTool(service)
    tool.set_context("telegram", "123")

    result = await tool.execute(
        action="add_inspection",
        name="nightly inspection",
        every_seconds=300,
    )
    assert "Created inspection job" in result

    jobs = service.list_jobs(include_disabled=True)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.payload.kind == "system_event"
    assert job.payload.message == "inspection:run"
    assert job.payload.channel == "telegram"
    assert job.payload.to == "123"


@pytest.mark.asyncio
async def test_cron_add_inspection_requires_schedule(tmp_path) -> None:
    service = CronService(tmp_path / "cron" / "jobs.json")
    tool = CronTool(service)
    tool.set_context("cli", "direct")

    result = await tool.execute(action="add_inspection")
    assert "either every_seconds, cron_expr, or at is required" in result


@pytest.mark.asyncio
async def test_cron_add_remains_agent_turn(tmp_path) -> None:
    service = CronService(tmp_path / "cron" / "jobs.json")
    tool = CronTool(service)
    tool.set_context("cli", "direct")

    result = await tool.execute(action="add", message="say hello", every_seconds=120)
    assert "Created job" in result

    jobs = service.list_jobs(include_disabled=True)
    assert len(jobs) == 1
    assert jobs[0].payload.kind == "agent_turn"
