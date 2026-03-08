"""Inspection analysis and reporting policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


DEFAULT_KEYWORDS = (
    "error",
    "failed",
    "failure",
    "panic",
    "critical",
    "exception",
    "timeout",
)


@dataclass
class InspectionCaseDraft:
    """Draft payload for turning one inspection result into a case."""

    title: str
    trigger: str
    source: str
    summary: str
    evidence: str
    conclusion: str
    suggestion: str
    status: str
    severity: str
    tags: list[str]


class InspectionPolicy:
    """Encapsulate inspection-specific analysis and reporting rules."""

    @staticmethod
    def keywords_for(target_keywords: list[str] | None) -> list[str]:
        return [k.lower() for k in (target_keywords or list(DEFAULT_KEYWORDS)) if k]

    @staticmethod
    def build_analysis_prompt(
        *,
        findings: list[dict[str, Any]],
        target_results: list[dict[str, Any]],
        target_errors: list[str],
    ) -> str:
        finding_text = "\n".join(
            f"- [{f['target']}:{f['line_no']}] {f['line'][:240]}" for f in findings[:80]
        )
        target_text = "\n".join(
            f"- {r.get('name', '')} ({r.get('kind', '')}): {len(r.get('matches', []))} matches"
            for r in target_results
        )
        error_text = "\n".join(f"- {e}" for e in target_errors) or "- none"
        return (
            "You are an SRE assistant. Summarize inspection findings in Chinese.\n"
            "Use sections: 概览, 重点异常, 可能原因, 建议动作.\n\n"
            f"Targets:\n{target_text}\n\n"
            f"Collector errors:\n{error_text}\n\n"
            f"Matched lines:\n{finding_text or '- none'}"
        )

    @staticmethod
    def render_report(
        *,
        started: datetime,
        trigger: str,
        target_results: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        target_errors: list[str],
        llm_summary: str,
    ) -> str:
        lines = [
            f"# Inspection Report ({started.strftime('%Y-%m-%d %H:%M:%S')})",
            "",
            "## Summary",
            f"- Trigger: {trigger}",
            f"- Targets: {len(target_results)}",
            f"- Findings: {len(findings)}",
            f"- Target Errors: {len(target_errors)}",
            "",
            "## Target Overview",
        ]
        if target_results:
            for result in target_results:
                lines.append(
                    f"- {result.get('name', '')} [{result.get('kind', '')}] "
                    f"matches={len(result.get('matches', []))}"
                )
                if result.get("error"):
                    lines.append(f"  collector_error: {result['error']}")
        else:
            lines.append("- No targets configured")

        lines += ["", "## Matched Lines"]
        if findings:
            for finding in findings[:200]:
                lines.append(f"- [{finding['target']}:{finding['line_no']}] {finding['line']}")
        else:
            lines.append("- No matched lines")

        lines += ["", "## Collector Errors"]
        if target_errors:
            for err in target_errors:
                lines.append(f"- {err}")
        else:
            lines.append("- None")

        lines += ["", "## Model Analysis", llm_summary or "Model analysis unavailable or skipped.", ""]
        return "\n".join(lines)

    @staticmethod
    def should_generate_case(*, mode: str, has_findings: bool) -> bool:
        if mode == "always":
            return True
        if mode == "error":
            return has_findings
        return False

    @staticmethod
    def build_case_draft(
        *,
        started: datetime,
        trigger: str,
        findings: list[dict[str, Any]],
        target_errors: list[str],
        report_path: str,
        llm_summary: str,
    ) -> InspectionCaseDraft:
        return InspectionCaseDraft(
            title=f"Inspection report {started.strftime('%Y-%m-%d %H:%M')}",
            trigger=trigger,
            source="inspection",
            summary=f"Inspection findings: {len(findings)}, target errors: {len(target_errors)}",
            evidence=f"Report path: {report_path}\n\n" + "\n".join(f["line"] for f in findings[:20]),
            conclusion=(llm_summary or "Please review report details.").strip()[:3000],
            suggestion="Prioritize high-frequency errors and verify affected components.",
            status="open" if findings else "resolved",
            severity="high" if findings else "low",
            tags=["inspection", "auto"],
        )
