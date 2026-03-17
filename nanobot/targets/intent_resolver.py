"""Lightweight natural-language target intent resolution."""

from __future__ import annotations

from dataclasses import dataclass

from nanobot.config.schema import TargetingConfig
from nanobot.targets.resolver import ResolvedTarget, resolve_targets


@dataclass(frozen=True)
class TargetIntentResolution:
    """Resolved multi-target expansion suggestion."""

    should_expand: bool
    reason: str = ""
    group_names: tuple[str, ...] = ()
    label_any: tuple[str, ...] = ()
    resolved_targets: tuple[ResolvedTarget, ...] = ()
    truncated: bool = False


def resolve_target_intent(
    text: str,
    targeting: TargetingConfig | None,
    *,
    max_targets: int = 5,
) -> TargetIntentResolution:
    """Resolve candidate multi-target scope from a user message."""
    if not targeting or not targeting.targets:
        return TargetIntentResolution(should_expand=False)

    normalized = text.strip().lower()
    if not normalized:
        return TargetIntentResolution(should_expand=False)

    matched_groups = tuple(
        group.name
        for group in targeting.groups
        if group.name.strip() and group.name.lower() in normalized
    )
    if matched_groups:
        resolved = tuple(resolve_targets(targeting, group_names=list(matched_groups)))
        return _finalize_resolution(
            resolved,
            reason=f"根据目标组匹配到 {', '.join(matched_groups)}",
            group_names=matched_groups,
            max_targets=max_targets,
        )

    known_labels = sorted(
        {
            label.strip().lower()
            for target in targeting.targets
            if target.enabled
            for label in target.labels
            if label.strip()
        }
    )
    matched_labels = tuple(label for label in known_labels if label in normalized)
    if matched_labels:
        resolved = tuple(resolve_targets(targeting, label_any=list(matched_labels)))
        return _finalize_resolution(
            resolved,
            reason=f"根据标签匹配到 {', '.join(matched_labels)}",
            label_any=matched_labels,
            max_targets=max_targets,
        )

    return TargetIntentResolution(should_expand=False)


def _finalize_resolution(
    resolved: tuple[ResolvedTarget, ...],
    *,
    reason: str,
    group_names: tuple[str, ...] = (),
    label_any: tuple[str, ...] = (),
    max_targets: int,
) -> TargetIntentResolution:
    if len(resolved) <= 1:
        return TargetIntentResolution(should_expand=False)

    truncated = len(resolved) > max_targets
    limited = resolved[:max_targets]
    return TargetIntentResolution(
        should_expand=True,
        reason=reason,
        group_names=group_names,
        label_any=label_any,
        resolved_targets=limited,
        truncated=truncated,
    )
