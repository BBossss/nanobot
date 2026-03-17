from nanobot.config.schema import TargetingConfig
from nanobot.targets.intent_resolver import resolve_target_intent


def test_resolve_target_intent_matches_group_name() -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1", "labels": ["storage", "hci"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["storage", "hci"]},
            ],
            "groups": [
                {"name": "storage-cluster", "targets": ["node-a", "node-b"]},
            ],
        }
    )

    result = resolve_target_intent("请检查 storage-cluster 的问题", targeting)

    assert result.should_expand is True
    assert result.group_names == ("storage-cluster",)
    assert [item.id for item in result.resolved_targets] == ["node-a", "node-b"]


def test_resolve_target_intent_matches_label_keyword() -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1", "labels": ["storage", "hci"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["storage", "hci"]},
                {"id": "node-c", "target": "root@10.0.0.3", "labels": ["compute", "hci"]},
            ]
        }
    )

    result = resolve_target_intent("storage 集群出问题了", targeting)

    assert result.should_expand is True
    assert result.label_any == ("storage",)
    assert [item.id for item in result.resolved_targets] == ["node-a", "node-b"]


def test_resolve_target_intent_returns_no_expansion_for_unknown_scope() -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1", "labels": ["storage", "hci"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["storage", "hci"]},
            ]
        }
    )

    result = resolve_target_intent("单节点日志看起来有问题", targeting)

    assert result.should_expand is False
    assert result.resolved_targets == ()


def test_resolve_target_intent_truncates_large_candidate_sets() -> None:
    targeting = TargetingConfig.model_validate(
        {
            "targets": [
                {"id": "node-a", "target": "root@10.0.0.1", "labels": ["storage"]},
                {"id": "node-b", "target": "root@10.0.0.2", "labels": ["storage"]},
                {"id": "node-c", "target": "root@10.0.0.3", "labels": ["storage"]},
            ]
        }
    )

    result = resolve_target_intent("storage 整体异常", targeting, max_targets=2)

    assert result.should_expand is True
    assert result.truncated is True
    assert [item.id for item in result.resolved_targets] == ["node-a", "node-b"]
