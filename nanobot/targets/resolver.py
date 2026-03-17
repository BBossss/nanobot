"""Deterministic multi-target resolver."""

from __future__ import annotations

from dataclasses import dataclass

from nanobot.config.schema import TargetDefinitionConfig, TargetingConfig


@dataclass(frozen=True)
class ResolvedTarget:
    """A normalized resolved target entry."""

    id: str
    target: str
    labels: tuple[str, ...]


def resolve_targets(
    targeting: TargetingConfig,
    *,
    target_ids: list[str] | None = None,
    group_names: list[str] | None = None,
    label_all: list[str] | None = None,
    label_any: list[str] | None = None,
) -> list[ResolvedTarget]:
    """Resolve targets from explicit IDs, groups, and label filters.

    Resolution order is deterministic and follows target declaration order.
    """
    enabled_targets = [t for t in targeting.targets if t.enabled]
    target_map = {t.id: t for t in enabled_targets}
    group_map = {g.name: g.targets for g in targeting.groups}

    selected_ids: set[str] = set()

    if not target_ids and not group_names:
        selected_ids = set(target_map.keys())
    else:
        for target_id in target_ids or []:
            if target_id not in target_map:
                raise ValueError(f"unknown target id: {target_id}")
            selected_ids.add(target_id)
        for group_name in group_names or []:
            if group_name not in group_map:
                raise ValueError(f"unknown target group: {group_name}")
            for target_id in group_map[group_name]:
                if target_id not in target_map:
                    raise ValueError(
                        f"group {group_name!r} includes disabled or unknown target id {target_id!r}"
                    )
                selected_ids.add(target_id)

    all_labels = {label.strip() for label in label_all or [] if label.strip()}
    any_labels = {label.strip() for label in label_any or [] if label.strip()}

    resolved: list[ResolvedTarget] = []
    for target in enabled_targets:
        if target.id not in selected_ids:
            continue
        labels = {label.strip() for label in target.labels if label.strip()}
        if all_labels and not all_labels.issubset(labels):
            continue
        if any_labels and labels.isdisjoint(any_labels):
            continue
        resolved.append(_to_resolved(target))

    return resolved


def _to_resolved(target: TargetDefinitionConfig) -> ResolvedTarget:
    return ResolvedTarget(
        id=target.id,
        target=target.target,
        labels=tuple(target.labels),
    )
