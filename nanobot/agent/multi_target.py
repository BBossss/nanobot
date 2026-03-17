"""Helpers for confirmation-gated multi-target troubleshooting."""

from __future__ import annotations

import re
from typing import Any, Awaitable, Callable


SUPPORTED_MULTI_TARGET_TOOLS = {
    "service_status",
    "process_snapshot",
    "search_log",
    "read_log_tail",
    "find_logs",
}


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

    for item in results:
        target_id = str(item.get("target_id", "unknown"))
        status = str(item.get("status", "ok"))
        if status != "ok":
            failures.append(f"- {target_id}: {item.get('error') or 'unknown error'}")
            continue
        signature = _normalize_content_signature(str(item.get("content", "")))
        signatures.setdefault(signature, []).append(target_id)

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

    return "\n".join(lines)


def _normalize_content_signature(content: str) -> str:
    """Strip target-specific prefixes so cross-target similarities can group together."""
    normalized = re.sub(r"\[target=[^\]]+\]\s*", "", content).strip()
    return normalized or "(empty)"
