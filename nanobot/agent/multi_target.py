"""Helpers for confirmation-gated multi-target troubleshooting."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from datetime import datetime
from typing import Any, Awaitable, Callable

from nanobot.agent.root_cause_candidates import (
    extract_candidate_signals,
    map_root_cause_candidates,
    render_candidate_root_causes,
)
from nanobot.agent.timeline import (
    TimelineArtifact,
    build_cross_target_timeline_artifact,
    build_log_timeline,
    extract_log_events,
)

SUPPORTED_MULTI_TARGET_TOOLS = {
    "service_status",
    "process_snapshot",
    "search_log",
    "read_log_tail",
}
LOG_MULTI_TARGET_TOOLS = {"search_log", "read_log_tail"}


@dataclass(slots=True)
class MultiTargetPerTargetResult:
    target_id: str
    target_host: str
    status: str
    content: str
    error: str
    observed_at: datetime


@dataclass(slots=True)
class MultiTargetFailedTarget:
    target_id: str
    target_host: str
    status: str
    error: str


@dataclass(slots=True)
class MultiTargetFinding:
    signature: str
    target_ids: list[str]
    target_hosts: list[str]
    count: int
    kind: str
    sample_evidence: str


@dataclass(slots=True)
class MultiTargetAggregation:
    tool_name: str
    targets_total: int
    ok_targets: list[str]
    failed_targets: list[MultiTargetFailedTarget]
    shared_findings: list[MultiTargetFinding]
    local_findings: list[MultiTargetFinding]
    per_target_results: list[MultiTargetPerTargetResult]
    _rendered_summary: str = field(default="", repr=False, compare=False)

    def __str__(self) -> str:
        return self._rendered_summary

    def __contains__(self, item: object) -> bool:
        if not isinstance(item, str):
            return False
        return item in self._rendered_summary

    def build_cross_target_timeline_artifact(
        self,
        *,
        incident: str | None = None,
        target_scope: str | None = None,
    ) -> TimelineArtifact | None:
        """Build a stable cross-target timeline artifact for log-oriented evidence."""
        if self.tool_name not in LOG_MULTI_TARGET_TOOLS:
            return None
        if target_scope is None:
            target_scope = ",".join(self.ok_targets) if self.ok_targets else None
        artifact = build_cross_target_timeline_artifact(
            tool_name=self.tool_name,
            results=[
                {
                    "target_id": result.target_id,
                    "target_host": result.target_host,
                    "status": result.status,
                    "content": result.content,
                    "error": result.error,
                    "observed_at": result.observed_at,
                }
                for result in self.per_target_results
            ],
            incident=incident,
            target_scope=target_scope,
        )
        return artifact if artifact.events else None

    def build_cross_target_timeline_summary(
        self,
        *,
        incident: str | None = None,
        target_scope: str | None = None,
    ) -> str | None:
        """Render a short cross-target timeline conclusion from log evidence."""
        if self.tool_name not in LOG_MULTI_TARGET_TOOLS:
            return None
        artifact = self.build_cross_target_timeline_artifact(
            incident=incident,
            target_scope=target_scope,
        )
        if artifact is None or not artifact.events:
            return None

        first_event = artifact.events[0]
        if first_event.scope not in {"shared", "near_shared"}:
            return None

        first_targets = _split_timeline_targets(first_event.target)
        if len(first_targets) < 2:
            return None

        first_time = _format_summary_timestamp(first_event.timestamp_normalized)
        first_phrase = _summarize_timeline_keyword(first_event.event)

        if first_event.scope == "shared":
            summary = (
                f"时间线补充：最早在 {first_time} 由 {','.join(first_targets)} "
                f"出现同类{first_phrase}"
            )
        else:
            summary = (
                f"时间线补充：最早在 {first_time} 由 {first_targets[0]} "
                f"出现{first_phrase}，{ '、'.join(first_targets[1:]) } "
                f"随后近同时出现同类异常"
            )

        later_local_event = _find_first_later_local_event(artifact.events[1:])
        if later_local_event is None:
            return summary + "。"

        later_time = _format_summary_timestamp(later_local_event.timestamp_normalized)
        later_targets = _split_timeline_targets(later_local_event.target)
        later_phrase = _summarize_timeline_keyword(later_local_event.event)
        if not later_targets:
            return summary + "。"
        return (
            f"{summary}；{later_time} 起 {','.join(later_targets)} "
            f"出现本地 {later_phrase}。"
        )


def supports_multi_target_tool(name: str) -> bool:
    """Return whether the tool should fan out across confirmed targets."""
    return name in SUPPORTED_MULTI_TARGET_TOOLS


async def execute_multi_target_tool(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    resolved_targets: list[dict[str, Any]],
    execute_tool: Callable[[str, dict[str, Any]], Awaitable[str]],
    on_target_progress: Callable[[int, int, str], Awaitable[None]] | None = None,
) -> str:
    """Execute one supported troubleshooting tool across multiple targets."""
    collected: list[dict[str, Any]] = []
    total = len(resolved_targets)
    for index, target in enumerate(resolved_targets, start=1):
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
        if on_target_progress:
            await on_target_progress(index, total, target["id"])
    summary = aggregate_multi_target_results(tool_name=tool_name, results=collected)
    rendered = [
        f"[multi-target][{item['target_id']} -> {item['target_host']}]\n"
        f"{item['error'] or item['content']}"
        for item in collected
    ]
    return str(summary) + "\n\n## Per-Target Results\n" + "\n\n".join(rendered)


def aggregate_multi_target_results(
    *,
    tool_name: str,
    results: list[dict[str, Any]],
) -> MultiTargetAggregation:
    """Build a compact multi-target summary for one tool invocation."""
    per_target_results: list[MultiTargetPerTargetResult] = []
    ok_targets: list[str] = []
    failed_targets: list[MultiTargetFailedTarget] = []
    grouped: dict[str, list[MultiTargetPerTargetResult]] = {}
    timeline_events = []

    for item in results:
        target_id = str(item.get("target_id", "unknown"))
        target_host = str(item.get("target_host", "unknown"))
        status = str(item.get("status", "ok"))
        content = str(item.get("content", ""))
        error = str(item.get("error", ""))
        observed_at = item.get("observed_at")
        if not isinstance(observed_at, datetime):
            observed_at = datetime.now()

        record = MultiTargetPerTargetResult(
            target_id=target_id,
            target_host=target_host,
            status=status,
            content=content,
            error=error,
            observed_at=observed_at,
        )
        per_target_results.append(record)

        if status != "ok":
            failed_targets.append(
                MultiTargetFailedTarget(
                    target_id=target_id,
                    target_host=target_host,
                    status=status,
                    error=error or "unknown error",
                )
            )
            continue

        ok_targets.append(target_id)
        signature = _normalize_content_signature(tool_name=tool_name, content=content)
        grouped.setdefault(signature, []).append(record)
        if tool_name in LOG_MULTI_TARGET_TOOLS:
            timeline_events.extend(
                extract_log_events(
                    target_id=target_id,
                    tool_name=tool_name,
                    content=content,
                    observed_at=observed_at,
                )
            )

    shared_findings: list[MultiTargetFinding] = []
    local_findings: list[MultiTargetFinding] = []
    for signature, records in grouped.items():
        target_ids = [record.target_id for record in records]
        target_hosts = [record.target_host for record in records]
        finding = MultiTargetFinding(
            signature=signature,
            target_ids=target_ids,
            target_hosts=target_hosts,
            count=len(records),
            kind="shared" if len(records) > 1 else "local",
            sample_evidence=signature,
        )
        if len(records) > 1:
            shared_findings.append(finding)
        else:
            local_findings.append(finding)

    aggregation = MultiTargetAggregation(
        tool_name=tool_name,
        targets_total=len(results),
        ok_targets=ok_targets,
        failed_targets=failed_targets,
        shared_findings=shared_findings,
        local_findings=local_findings,
        per_target_results=per_target_results,
    )
    rendered = _render_multi_target_summary(
        aggregation=aggregation,
        timeline_events=timeline_events,
    )
    aggregation._rendered_summary = rendered
    return aggregation


def _render_multi_target_summary(
    *,
    aggregation: MultiTargetAggregation,
    timeline_events: list[Any],
) -> str:
    failed_count = len(aggregation.failed_targets)
    ok_count = len(aggregation.ok_targets)
    lines = [
        f"## Multi-Target Summary: {aggregation.tool_name}",
        f"Targets: {aggregation.targets_total} total, {ok_count} ok, {failed_count} failed",
    ]
    if aggregation.shared_findings or aggregation.local_findings:
        if aggregation.shared_findings:
            lines.append("### Shared Findings")
            for finding in aggregation.shared_findings:
                lines.append(f"- {', '.join(finding.target_ids)}: {finding.signature}")
        if aggregation.local_findings:
            lines.append("### Local Findings")
            for finding in aggregation.local_findings:
                lines.append(f"- {finding.target_ids[0]}: {finding.signature}")
    else:
        lines.append("- No successful target results.")

    if aggregation.failed_targets:
        lines.append("### Failed Targets")
        for failed in aggregation.failed_targets:
            lines.append(f"- {failed.target_id}: {failed.error}")

    if aggregation.tool_name in LOG_MULTI_TARGET_TOOLS and timeline_events:
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
    if not any(
        marker in "\n".join(lines)
        for marker in ("### Shared Findings", "### Failed Targets", "## Timeline")
    ):
        return ""
    summary_text = "\n".join(lines)
    extracted = extract_candidate_signals(summary_text)
    candidates = map_root_cause_candidates(extracted)
    rendered = render_candidate_root_causes(candidates)
    if "当前证据不足以形成候选根因" in rendered:
        return ""
    return rendered


def _split_timeline_targets(target: str | None) -> list[str]:
    if not target:
        return []
    return [item.strip() for item in target.split(",") if item.strip()]


def _find_first_later_local_event(
    events: list[Any],
) -> Any | None:
    for event in events:
        if getattr(event, "scope", None) == "local":
            return event
    return None


def _format_summary_timestamp(timestamp_normalized: str | None) -> str:
    if not timestamp_normalized:
        return ""
    try:
        return datetime.fromisoformat(timestamp_normalized).strftime("%H:%M:%S")
    except ValueError:
        match = re.search(r"(\d{2}:\d{2}:\d{2})", timestamp_normalized)
        if match is not None:
            return match.group(1)
    return timestamp_normalized


def _summarize_timeline_keyword(text: str) -> str:
    lowered = text.lower()
    if "timeout" in lowered or "超时" in text:
        return "超时"
    if "permission denied" in lowered:
        return "permission denied"
    if "connection refused" in lowered:
        return "connection refused"
    return text.strip() or "异常"
