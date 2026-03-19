"""Confirmation-gated troubleshooting targeting helpers."""

from __future__ import annotations

from typing import Any, Callable

from nanobot.agent.workflow import control as workflow_control
from nanobot.session.manager import Session


def workflow_forbids_multi_target(session: Session) -> bool:
    """Return whether workflow scope constraints currently forbid multi-target expansion."""
    constraints = session.metadata.get("workflow_scope_constraints")
    return isinstance(constraints, dict) and constraints.get("forbid_multi_target") is True


def workflow_allows_confirmed_multi_target(session: Session | None) -> bool:
    """Return whether a confirmed multi-target scope may be reused for this turn."""
    if session is None:
        return False
    return (
        session.metadata.get("expansion_confirmed") is True
        and not workflow_forbids_multi_target(session)
    )


def handle_target_expansion_gate(
    session: Session,
    content: str,
    *,
    resolve_target_intent: Callable[[str], dict[str, Any] | None],
    clear_confirmed_target_scope: Callable[[Session], None],
) -> str | None:
    """Handle confirmation-gated cluster expansion before normal agent execution."""
    if session.metadata.pop("expansion_skip_reprompt_once", False):
        return None

    pending = session.metadata.get("pending_target_resolution")
    token = workflow_control.normalized_reply_token(content)
    if pending:
        # A pending multi-target confirmation gate takes precedence over
        # workflow-control parsing for exact replies such as "继续".
        if token in {"确认", "继续", "可以查", "yes", "y"}:
            session.metadata["resolved_target_ids"] = list(pending.get("resolved_target_ids", []))
            session.metadata["resolved_targets"] = list(pending.get("resolved_targets", []))
            session.metadata["resolution_reason"] = str(pending.get("reason", ""))
            session.metadata["expansion_confirmed"] = True
            session.metadata["pending_target_resolution"] = None
            if token == "继续":
                session.metadata["workflow_paused"] = False
                session.metadata["workflow_last_control_input"] = "继续"
            session.metadata["workflow_skip_control_once"] = True
            return None
        if token in {"不用", "先单节点", "no", "n"}:
            session.metadata["pending_target_resolution"] = None
            clear_confirmed_target_scope(session)
            return "保持单节点排障模式。如需多节点排查，我会先列出候选节点再请你确认。"

    if workflow_forbids_multi_target(session):
        return None

    resolution = resolve_target_intent(content)
    if not resolution:
        return None

    session.metadata["pending_target_resolution"] = resolution
    session.metadata["expansion_confirmed"] = False
    targets = ", ".join(resolution["resolved_target_ids"])
    suffix = "。候选范围已截断。" if resolution.get("truncated") else "。"
    return (
        f"{resolution['reason']}，候选节点为 {targets}{suffix}"
        " 如果要切换到多节点排查，请回复“确认”。当前仍保持单节点模式。"
    )


def build_confirmed_scope_progress(session: Session) -> str | None:
    """Build a progress note for a confirmed multi-target troubleshooting scope."""
    if not workflow_allows_confirmed_multi_target(session):
        return None
    target_ids = session.metadata.get("resolved_target_ids") or []
    if not target_ids:
        return None
    reason = str(session.metadata.get("resolution_reason", "")).strip()
    prefix = "已确认多节点排查范围"
    if reason:
        return f"{prefix}：{', '.join(target_ids)}。依据：{reason}"
    return f"{prefix}：{', '.join(target_ids)}。"


def clear_confirmed_target_scope(session: Session, *, skip_reprompt_once: bool) -> None:
    """Clear confirmed multi-target scope after it has been used or rejected."""
    session.metadata["expansion_confirmed"] = False
    session.metadata.pop("resolved_target_ids", None)
    session.metadata.pop("resolved_targets", None)
    session.metadata.pop("resolution_reason", None)
    if skip_reprompt_once:
        session.metadata["expansion_skip_reprompt_once"] = True
    else:
        session.metadata.pop("expansion_skip_reprompt_once", None)
