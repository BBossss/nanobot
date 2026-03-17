from pathlib import Path

import pytest

from nanobot.config.schema import Config, InspectionTargetConfig, TargetingConfig
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
async def test_inspection_multi_target_group_executes_same_profile(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)

    log_file = tmp_path / "cluster.log"
    log_file.write_text("ok\nERROR timeout\n", encoding="utf-8")
    cfg.inspection.targets = [
        InspectionTargetConfig(
            name="cluster-log",
            kind="log_file",
            path=str(log_file),
            target_groups=["hci-cluster-a"],
            max_lines=100,
            max_matches=10,
        )
    ]
    cfg.targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "local", "labels": ["hci", "storage"]},
                {"id": "node-b", "target": "local", "labels": ["hci", "compute"]},
            ],
            "groups": [
                {"name": "hci-cluster-a", "targets": ["node-a", "node-b"]},
            ],
        }
    )

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
    assert result["targets"] == 2
    assert result["profiles"] == 1
    assert result["findings"] == 2
    assert result["target_status"] == {"ok": 2, "failed": 0, "skipped": 0}

    report = Path(result["report_path"]).read_text(encoding="utf-8")
    assert "node-a (local)" in report
    assert "node-b (local)" in report
    assert "[node-a/cluster-log:" in report
    assert "[node-b/cluster-log:" in report


@pytest.mark.asyncio
async def test_inspection_multi_target_remote_is_marked_skipped(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)

    log_file = tmp_path / "cluster.log"
    log_file.write_text("ERROR timeout\n", encoding="utf-8")
    cfg.inspection.targets = [
        InspectionTargetConfig(
            name="cluster-log",
            kind="log_file",
            path=str(log_file),
            target_groups=["mixed-cluster"],
            max_lines=100,
            max_matches=10,
        )
    ]
    cfg.targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "local", "labels": ["hci"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["hci"]},
            ],
            "groups": [
                {"name": "mixed-cluster", "targets": ["node-a", "node-b"]},
            ],
        }
    )

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
    assert result["targets"] == 2
    assert result["target_status"]["ok"] == 1
    assert result["target_status"]["skipped"] == 1
    assert result["target_errors"] == 1
