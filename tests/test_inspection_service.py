import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nanobot.cli.commands import app
from nanobot.config.schema import Config, ExecToolConfig, InspectionTargetConfig
from nanobot.inspection.service import InspectionService


runner = CliRunner()


def _build_config(tmp_path: Path) -> Config:
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path)
    cfg.cases.path = str(tmp_path / "notes" / "cases")
    cfg.inspection.enabled = True
    cfg.inspection.report_dir = str(tmp_path / "reports" / "inspection")
    cfg.inspection.generate_case_on = "error"
    return cfg


@pytest.mark.asyncio
async def test_inspection_run_from_log_file_generates_report_and_case(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)
    log_file = tmp_path / "var.log"
    log_file.write_text("ok line\nERROR disk failed\nnormal\n", encoding="utf-8")
    cfg.inspection.targets = [
        InspectionTargetConfig(
            name="main-log",
            kind="log_file",
            path=str(log_file),
            max_lines=100,
            max_matches=10,
        )
    ]
    service = InspectionService(
        workspace=cfg.workspace_path,
        inspection=cfg.inspection,
        provider=None,
        model=None,
        cases=cfg.cases,
    )

    result = await service.run(trigger="manual")
    assert result["status"] == "ok"
    assert result["targets"] == 1
    assert result["findings"] == 1
    assert result["case_id"].startswith("INC-")
    assert Path(result["report_path"]).exists()


@pytest.mark.asyncio
async def test_inspection_run_with_command_target_error_is_degraded(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)
    cfg.inspection.targets = [
        InspectionTargetConfig(
            name="bad-cmd",
            kind="command",
            command="definitely-not-a-command-xyz",
            max_lines=100,
            max_matches=10,
        )
    ]

    service = InspectionService(
        workspace=cfg.workspace_path,
        inspection=cfg.inspection,
        provider=None,
        model=None,
        cases=cfg.cases,
    )
    result = await service.run(trigger="cron")
    assert result["status"] == "ok"
    assert result["findings"] == 0
    assert result["target_errors"] == 1
    assert Path(result["report_path"]).exists()


@pytest.mark.asyncio
async def test_inspection_command_target_respects_exec_readonly_guard(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)
    cfg.inspection.targets = [
        InspectionTargetConfig(
            name="restart-attempt",
            kind="command",
            command="systemctl restart kubelet",
            max_lines=100,
            max_matches=10,
        )
    ]

    service = InspectionService(
        workspace=cfg.workspace_path,
        inspection=cfg.inspection,
        provider=None,
        model=None,
        cases=cfg.cases,
        exec_config=ExecToolConfig(
            readonly_mode=True,
            allowed_commands=["ls", "cat"],
            approval_file=str(tmp_path / "approvals.json"),
        ),
    )
    result = await service.run(trigger="cron")
    assert result["status"] == "ok"
    assert result["findings"] == 0
    assert result["target_errors"] == 1

    report = Path(result["report_path"]).read_text(encoding="utf-8")
    assert "manual approval" in report

    audit_file = tmp_path / "audit" / "commands.jsonl"
    assert audit_file.exists()
    payload = json.loads(audit_file.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["source"] == "inspection.command"
    assert payload["status"] == "blocked"
    assert payload["metadata"]["target"] == "restart-attempt"


def test_inspection_cli_run(tmp_path: Path, monkeypatch) -> None:
    cfg = _build_config(tmp_path)
    log_file = tmp_path / "app.log"
    log_file.write_text("all good\ncritical timeout in storage path\n", encoding="utf-8")
    cfg.inspection.targets = [
        InspectionTargetConfig(
            name="app-log",
            kind="log_file",
            path=str(log_file),
            max_lines=50,
            max_matches=5,
        )
    ]
    monkeypatch.setattr("nanobot.config.loader.load_config", lambda: cfg)

    result = runner.invoke(app, ["inspection", "run", "--no-llm"])
    assert result.exit_code == 0
    assert "Inspection done" in result.stdout
    assert "findings=1" in result.stdout
