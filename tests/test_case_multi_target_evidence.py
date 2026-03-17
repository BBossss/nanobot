from pathlib import Path

import pytest

from nanobot.cases.store import CaseStore
from nanobot.config.schema import Config, InspectionTargetConfig, TargetingConfig
from nanobot.inspection.service import InspectionService


def _build_config(tmp_path: Path) -> Config:
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path)
    cfg.cases.path = str(tmp_path / "notes" / "cases")
    cfg.inspection.enabled = True
    cfg.inspection.report_dir = str(tmp_path / "reports" / "inspection")
    cfg.inspection.generate_case_on = "error"
    return cfg


@pytest.mark.asyncio
async def test_inspection_case_contains_multi_target_evidence_links(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)
    log_file = tmp_path / "cluster.log"
    log_file.write_text("INFO healthy\nERROR quorum timeout\n", encoding="utf-8")

    cfg.targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "local", "labels": ["hci", "storage"]},
                {"id": "node-b", "target": "local", "labels": ["hci", "storage"]},
            ],
            "groups": [
                {"name": "cluster-a", "targets": ["node-a", "node-b"]},
            ],
        }
    )
    cfg.inspection.targets = [
        InspectionTargetConfig(
            name="cluster-log",
            kind="log_file",
            path=str(log_file),
            target_groups=["cluster-a"],
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
        targeting=cfg.targeting,
    )
    result = await service.run(trigger="manual")

    assert result["status"] == "ok"
    assert result["case_id"].startswith("INC-")

    case_store = CaseStore(cfg.workspace_path, cfg.cases.path)
    _, content = case_store.get_case(result["case_id"])
    assert content is not None
    assert "targets: node-a, node-b" in content
    assert "[node-a/cluster-log:" in content
    assert "[node-b/cluster-log:" in content
