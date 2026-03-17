import pytest

from nanobot.config.schema import Config, TargetingConfig
from nanobot.targets.resolver import resolve_targets


def test_targeting_config_rejects_unknown_group_reference() -> None:
    with pytest.raises(ValueError, match="references unknown target id"):
        Config.model_validate(
            {
                "targeting": {
                    "targets": [
                        {"id": "node-a", "target": "root@10.0.0.1", "labels": ["hci", "storage"]},
                    ],
                    "groups": [
                        {"name": "cluster-a", "targets": ["node-a", "node-missing"]},
                    ],
                }
            }
        )


def test_targeting_config_rejects_duplicate_target_ids() -> None:
    with pytest.raises(ValueError, match="duplicate target id"):
        Config.model_validate(
            {
                "targeting": {
                    "targets": [
                        {"id": "node-a", "target": "root@10.0.0.1"},
                        {"id": "node-a", "target": "root@10.0.0.2"},
                    ]
                }
            }
        )


def test_resolve_targets_returns_all_enabled_by_default() -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1", "labels": ["hci", "storage"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["hci", "compute"]},
                {"id": "node-c", "target": "root@10.0.0.3", "labels": ["backup"], "enabled": False},
            ]
        }
    )

    resolved = resolve_targets(targeting)

    assert [item.id for item in resolved] == ["node-a", "node-b"]


def test_resolve_targets_by_group_and_label_is_deterministic() -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1", "labels": ["hci", "storage"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["hci", "compute"]},
                {"id": "node-c", "target": "root@10.0.0.3", "labels": ["hci", "storage", "hot"]},
            ],
            "groups": [
                {"name": "cluster-a", "targets": ["node-b", "node-a", "node-c"]},
            ],
        }
    )

    resolved = resolve_targets(
        targeting,
        group_names=["cluster-a"],
        label_all=["hci", "storage"],
    )

    assert [item.id for item in resolved] == ["node-a", "node-c"]


def test_resolve_targets_unknown_selector_errors() -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1"},
            ],
            "groups": [
                {"name": "cluster-a", "targets": ["node-a"]},
            ],
        }
    )

    with pytest.raises(ValueError, match="unknown target id"):
        resolve_targets(targeting, target_ids=["node-x"])

    with pytest.raises(ValueError, match="unknown target group"):
        resolve_targets(targeting, group_names=["cluster-x"])
