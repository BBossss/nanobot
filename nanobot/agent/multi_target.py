"""Helpers for confirmation-gated multi-target troubleshooting."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Awaitable, Callable

from nanobot.agent.root_cause_candidates import (
    extract_candidate_signals,
    map_root_cause_candidates,
    render_candidate_root_causes,
)
from nanobot.agent.timeline import build_log_timeline, extract_log_events

SUPPORTED_MULTI_TARGET_TOOLS = {
    "service_status",
    "process_snapshot",
    "search_log",
    "read_log_tail",
    "find_logs",
}
LOG_MULTI_TARGET_TOOLS = {"search_log", "read_log_tail"}


def supports_multi_target_tool(name: str) -> bool:
    """Return whether the tool should fan out across confirmed targets."""
    return name in SUPPORTED_MULTI_TARGET_TOOLS


async def execute_multi_target_tool(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    resolved_targets: list[dict[str, Any]],
    execute_tool: Callable[[str, dict[str, Any]], Awaitable[str]],
) -> str:
    """Execute one supported troubleshooting tool across multiple targets."""
    collected: list[dict[str, Any]] = []
    for target in resolved_targets:
        params = dict(arguments)
        params["target"] = target["target"]
        result = await execute_tool(tool_name, params)
        error = result if isinstance(result, str) and result.startswith("Error") else ""
        collected.append(
            {
                "target_id": target["id"],
                "target_host": target["target"],
                "status": "error" if error else "ok",
                "content": "" if error else result,
                "error": error,
                "observed_at": datetime.now(),
            }
        )
    summary = aggregate_multi_target_results(tool_name=tool_name, results=collected)
    rendered = [
        f"[multi-target][{item['target_id']} -> {item['target_host']}]\n"
        f"{item['error'] or item['content']}"
        for item in collected
    ]
    return summary + "\n\n## Per-Target Results\n" + "\n\n".join(rendered)


def aggregate_multi_target_results(*, tool_name: str, results: list[dict[str, Any]]) -> str:
    """Build a compact multi-target summary for one tool invocation."""
    signatures: dict[str, list[str]] = {}
    failures: list[str] = []
    timeline_events = []

    for item in results:
        target_id = str(item.get("target_id", "unknown"))
        status = str(item.get("status", "ok"))
        if status != "ok":
            failures.append(f"- {target_id}: {item.get('error') or 'unknown error'}")
            continue
        signature = _normalize_content_signature(
            tool_name=tool_name,
            content=str(item.get("content", "")),
        )
        signatures.setdefault(signature, []).append(target_id)
        if tool_name in LOG_MULTI_TARGET_TOOLS:
            observed_at = item.get("observed_at")
            if not isinstance(observed_at, datetime):
                observed_at = datetime.now()
            timeline_events.extend(
                extract_log_events(
                    target_id=target_id,
                    tool_name=tool_name,
                    content=str(item.get("content", "")),
                    observed_at=observed_at,
                )
            )

    lines = [f"## Multi-Target Summary: {tool_name}"]
    if signatures:
        common = {sig: targets for sig, targets in signatures.items() if len(targets) > 1}
        local = {sig: targets for sig, targets in signatures.items() if len(targets) == 1}
        if common:
            lines.append("### Common Findings")
            for sig, targets in common.items():
                lines.append(f"- {', '.join(targets)}: {sig}")
        if local:
            lines.append("### Local Findings")
            for sig, targets in local.items():
                lines.append(f"- {targets[0]}: {sig}")
    else:
        lines.append("- No successful target results.")

    if failures:
        lines.append("### Failed Targets")
        lines.extend(failures)

    timeline_summary = ""
    if tool_name in LOG_MULTI_TARGET_TOOLS and timeline_events:
        timeline_summary = build_log_timeline(timeline_events)
        if timeline_summary:
            lines.extend(["", timeline_summary])

    candidate_summary = _build_candidate_root_cause_summary(lines)
    if candidate_summary:
        lines.extend(["", candidate_summary])

    return "\n".join(lines)


def _normalize_content_signature(*, tool_name: str, content: str) -> str:
    """Strip target-specific and log-format noise so cross-target similarities group together."""
    normalized = re.sub(r"\[target=[^\]]+\]\s*", "", content).strip()
    if tool_name in LOG_MULTI_TARGET_TOOLS:
        normalized = _normalize_log_content_signature(normalized)
    return normalized or "(empty)"


def _normalize_log_content_signature(content: str) -> str:
    lines: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _is_log_header_line(line):
            continue
        line = re.sub(r"^\d+:\s*", "", line)
        line = re.sub(r"^\d{4}[-/]\d{2}[-/]\d{2} \d{2}:\d{2}:\d{2}\s*", "", line)
        if line:
            lines.append(line)
    return "\n".join(lines).strip() or "(empty)"


def _is_log_header_line(line: str) -> bool:
    return bool(
        re.match(r"^tail\s+\d+\s+lines\s+from\s+.+:$", line)
        or re.match(r"^Found(?:\s+\d+\s+match\(es\))?\s+in\s+.+:$", line)
    )


def _build_candidate_root_cause_summary(lines: list[str]) -> str:
    summary_text = "\n".join(lines)
    extracted = extract_candidate_signals(summary_text)
    candidates = map_root_cause_candidates(extracted)
    rendered = render_candidate_root_causes(candidates)
    if "当前证据不足以形成候选根因" in rendered:
        return ""
    return rendered
