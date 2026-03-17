"""Evidence-driven candidate root cause generation."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedSignals:
    signals: tuple[str, ...]
    evidence_lines: tuple[str, ...]


@dataclass(frozen=True)
class RootCauseCandidate:
    candidate_type: str
    evidence_lines: tuple[str, ...]


def extract_candidate_signals(summary: str) -> ExtractedSignals:
    """Extract bounded signals from current evidence text."""
    normalized = summary.lower()
    signals: set[str] = set()

    if any(token in normalized for token in ("timeout", "timed out")):
        signals.add("timeout")
    if "refused" in normalized:
        signals.add("connection_refused")
    if "unreachable" in normalized:
        signals.add("unreachable")
    if any(token in normalized for token in ("retry exceeded", "retried", "exceeded", "retry")):
        signals.add("retry_exhausted")
    if any(token in normalized for token in ("crash", "panic", "exit", "failed")):
        signals.add("service_exit")
    if any(token in normalized for token in ("backend", "upstream", "dependency", "storage backend")):
        signals.add("dependency_backend")
    if "common findings" in normalized or "concurrent / near events" in normalized:
        signals.add("cross_node_common")
    if "local findings" in normalized:
        signals.add("single_node_only")

    evidence_lines = tuple(
        line.strip()
        for line in summary.splitlines()
        if line.strip().startswith("- ")
    )
    if any(_line_mentions_multiple_targets(line) for line in evidence_lines):
        signals.add("cross_node_common")
    return ExtractedSignals(signals=tuple(sorted(signals)), evidence_lines=evidence_lines)


def map_root_cause_candidates(extracted: ExtractedSignals) -> list[RootCauseCandidate]:
    """Map extracted signals to a fixed candidate type set."""
    signals = set(extracted.signals)
    candidates: list[RootCauseCandidate] = []

    if ("timeout" in signals or "connection_refused" in signals or "unreachable" in signals) and "cross_node_common" in signals:
        candidates.append(
            RootCauseCandidate(
                candidate_type="跨节点共享连接/超时异常",
                evidence_lines=_pick_evidence(extracted.evidence_lines, ("timeout", "refused", "unreachable")),
            )
        )
    if "single_node_only" in signals and "cross_node_common" not in signals and ("timeout" in signals or "service_exit" in signals):
        candidates.append(
            RootCauseCandidate(
                candidate_type="局部节点异常",
                evidence_lines=_pick_evidence(extracted.evidence_lines, ("node-", "timeout", "failed", "crash")),
            )
        )
    if "service_exit" in signals:
        candidates.append(
            RootCauseCandidate(
                candidate_type="服务执行失败/异常退出",
                evidence_lines=_pick_evidence(extracted.evidence_lines, ("failed", "exit", "crash", "panic")),
            )
        )
    if "retry_exhausted" in signals:
        candidates.append(
            RootCauseCandidate(
                candidate_type="重试耗尽/任务卡住",
                evidence_lines=_pick_evidence(extracted.evidence_lines, ("retry", "exceeded", "stuck")),
            )
        )
    if "dependency_backend" in signals and ("timeout" in signals or "connection_refused" in signals or "unreachable" in signals):
        candidates.append(
            RootCauseCandidate(
                candidate_type="依赖不可达或下游异常",
                evidence_lines=_pick_evidence(extracted.evidence_lines, ("backend", "upstream", "dependency", "storage backend")),
            )
        )

    deduped: list[RootCauseCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.candidate_type in seen:
            continue
        if len(candidate.evidence_lines) < 1:
            continue
        seen.add(candidate.candidate_type)
        deduped.append(candidate)
        if len(deduped) >= 2:
            break
    return deduped


def render_candidate_root_causes(candidates: list[RootCauseCandidate]) -> str:
    """Render constrained candidate root cause output."""
    if not candidates:
        return "当前证据不足以形成候选根因。"

    lines = ["## Candidate Root Cause"]
    for candidate in candidates:
        lines.append(f"- 候选根因：{candidate.candidate_type}")
    lines.append("")
    lines.append("## Supporting Evidence")
    for candidate in candidates:
        lines.append(f"- {candidate.candidate_type}")
        for evidence in candidate.evidence_lines[:4]:
            lines.append(f"  {evidence}")
    rendered = "\n".join(lines)
    return rendered.replace("已确认根因", "候选根因")


def _pick_evidence(lines: tuple[str, ...], keywords: tuple[str, ...]) -> tuple[str, ...]:
    picked = [
        line for line in lines
        if any(re.search(re.escape(keyword), line, re.IGNORECASE) for keyword in keywords)
    ]
    return tuple(picked[:4])


def _line_mentions_multiple_targets(line: str) -> bool:
    return len(re.findall(r"node-[\w-]+", line, re.IGNORECASE)) >= 2
