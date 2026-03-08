"""Case recording policy extracted from AgentLoop."""

from __future__ import annotations

from dataclasses import dataclass


END_MARKERS = (
    "结束",
    "查完了",
    "完成排查",
    "排查完成",
    "故障已恢复",
    "归档",
    "生成案例摘要",
    "保存案例",
    "保存摘要",
    "总结并保存",
    "done",
    "wrap up",
)


@dataclass
class CaseRecordDraft:
    """Draft payload for writing one generated case."""

    title: str
    trigger: str
    source: str
    summary: str
    evidence: str
    conclusion: str
    suggestion: str
    status: str
    tags: list[str]


class CaseRecordPolicy:
    """Encapsulate case recording rules and default content shaping."""

    @staticmethod
    def should_record(content: str, mode: str) -> bool:
        if mode == "manual":
            return False
        if mode == "every_turn":
            return True

        text = (content or "").strip()
        if not text:
            return False
        lower = text.lower()

        if "?" in text or "？" in text or lower.endswith("吗"):
            return False

        return any(mark in lower for mark in END_MARKERS)

    @staticmethod
    def build_generated_case(*, channel: str, content: str, final_content: str) -> CaseRecordDraft:
        summary = (content or "")[:3000]
        conclusion = (final_content or "")[:3000]
        title = summary.splitlines()[0].strip() if summary.strip() else "Troubleshooting case"
        title = title[:120] or "Troubleshooting case"
        tags = [channel] if channel else ["troubleshooting"]
        return CaseRecordDraft(
            title=title,
            trigger=channel,
            source="generated",
            summary=summary,
            evidence="Collected from request/response flow",
            conclusion=conclusion,
            suggestion="Review results and continue with next checks if needed",
            status="open",
            tags=tags,
        )

    @staticmethod
    def build_history_entry(*, created_at: str, case_id: str, channel: str, title: str, conclusion: str) -> str:
        return (
            f"[{created_at[:16]}] CASE {case_id} | "
            f"channel={channel} | title={title} | "
            f"conclusion={conclusion[:160]}"
        )
