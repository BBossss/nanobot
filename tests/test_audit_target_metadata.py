import json
from pathlib import Path

import pytest

from nanobot.config.schema import Config, ExecToolConfig, InspectionTargetConfig, TargetingConfig
from nanobot.inspection.service import InspectionService


def _build_config(tmp_path: Path) -> Config:
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path)
    cfg.cases.path = str(tmp_path / "notes" / "cases")
    cfg.inspection.enabled = True
    cfg.inspection.report_dir = str(tmp_path / "reports" / "inspection")
    cfg.inspection.generate_case_on = "never"
    return cfg


@pytest.mark.asyncio
async def test_inspection_audit_contains_target_identity_metadata(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)
    cfg.targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "local", "labels": ["hci"]},
            ]
        }
    )
    cfg.inspection.targets = [
        InspectionTargetConfig(
            name="restart-attempt",
            kind="command",
            command="systemctl restart kubelet",
            target_ids=["node-a"],
        )
    ]

    service = InspectionService(
        workspace=cfg.workspace_path,
        inspection=cfg.inspection,
        provider=None,
        model=None,
        cases=cfg.cases,
        targeting=cfg.targeting,
        exec_config=ExecToolConfig(
            readonly_mode=True,
            allowed_commands=["ls", "cat"],
            approval_file=str(tmp_path / "approvals.json"),
        ),
    )
    result = await service.run(trigger="cron")
    assert result["status"] == "ok"
    assert result["target_errors"] == 1

    audit_file = tmp_path / "audit" / "commands.jsonl"
    payload = json.loads(audit_file.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["source"] == "inspection.command"
    assert payload["command"] == "systemctl restart kubelet"
    assert payload["status"] == "blocked"
    assert payload["timestamp"]
    assert payload["metadata"]["target_id"] == "node-a"
    assert payload["metadata"]["executor"] == "inspection"
    assert payload["metadata"]["result"] == "blocked"
