"""Troubleshooting result shaping helpers."""

from __future__ import annotations

import re
from typing import Any

from nanobot.agent.context import ContextBuilder
from nanobot.agent.workflow import control as workflow_control
from nanobot.agent.workflow import targeting as workflow_targeting
from nanobot.session.manager import Session

OUTPUT_KIND_TROUBLESHOOTING_REPLY = "troubleshooting_reply"
OUTPUT_KIND_INSPECTION_ARTIFACT = "inspection_artifact"
OUTPUT_KIND_REPORT_ARTIFACT = "report_artifact"
OUTPUT_KIND_CASE_ARTIFACT = "case_artifact"
OUTPUT_KIND_TIMELINE_ARTIFACT = "timeline_artifact"
OUTPUT_KIND_ROOT_CAUSE_CANDIDATE = "root_cause_candidate"
OUTPUT_KIND_GENERIC_REPLY = "generic_reply"


def normalize_kind_marker(value: str) -> str:
    """Normalize lightweight kind markers across headings and frontmatter values."""
    normalized = value.strip().strip("\"'").lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    return normalized


def build_workflow_runtime_context(session: Session, content: str | None = None) -> str | None:
    """Build bounded workflow hints that shape investigation planning for this turn."""
    lines: list[str] = []
    focus_hint = session.metadata.get("workflow_focus_hint")
    if focus_hint == "logs_only":
        lines.append(
            "- Focus hint: prioritize log-oriented readonly checks first when choosing the next step; "
            "keep using judgment and switch direction if logs are insufficient."
        )
    if workflow_targeting.workflow_forbids_multi_target(session):
        lines.append(
            "- Scope constraint: stay in single-target troubleshooting mode for this turn; "
            "do not expand or reuse multi-target scope unless the user explicitly changes it."
        )
    if (
        session.metadata.get("workflow_result_mode") == "evidence_first"
        and content is not None
        and workflow_control.looks_like_troubleshooting_content(content)
    ):
        lines.append(
            "- Result shaping: 证据优先收口会改变结果收口方式，但不改变调查动作选择。 "
            "This only changes how the result is presented; 调查动作选择仍然是判断驱动的，不因该模式改变。"
        )
    if not lines:
        return None
    return (
        ContextBuilder._RUNTIME_CONTEXT_TAG
        + "\nWorkflow Controls:\n"
        + "\n".join(lines)
    )


def looks_like_structured_artifact_body(content: str) -> bool:
    """Return whether the reply looks like a structured artifact body that should stay untouched."""
    text = content.strip()
    if not text:
        return False
    if re.search(r"(?im)^#{1,6}\s+(inspection|report|case|timeline|root cause candidate)\b", text):
        return True
    if has_frontmatter_kind_marker(
        text,
        "inspection",
        "report",
        "case",
        "timeline",
        "event_timeline",
        "root_cause_candidate",
        "root cause candidate",
    ):
        return True
    if re.search(r"(?m)^\s*-\s+\[[^\]]+\]\s+\S", text):
        return True
    if looks_like_timeline_artifact(text) or looks_like_root_cause_candidate(text):
        return True
    return False


def extract_frontmatter_fields(content: str) -> dict[str, str]:
    """Extract simple frontmatter fields from the top of a structured body."""
    text = content.strip()
    if not text.startswith("---\n"):
        return {}
    match = re.match(r"(?s)^---\n(?P<body>.*?)\n---(?:\n|$)", text)
    if match is None:
        return {}
    fields: dict[str, str] = {}
    for line in match.group("body").splitlines():
        field_match = re.match(r"\s*([A-Za-z][\w\- ]{0,40}):\s*(.+?)\s*$", line)
        if field_match is None:
            continue
        key = field_match.group(1).strip().lower().replace(" ", "_")
        fields[key] = field_match.group(2).strip().lower()
    return fields


def extract_top_level_key_names(content: str) -> set[str]:
    """Extract top-level key names from a key/value artifact body."""
    keys: set[str] = set()
    for line in content.strip().splitlines():
        match = re.match(r"\s*([A-Za-z][\w\- ]{0,40}):\s+\S+", line)
        if match is None:
            continue
        keys.add(match.group(1).strip().lower().replace(" ", "_"))
    return keys


def looks_like_generic_structured_body(content: str) -> bool:
    """Return whether the content has a generic structured-body shape."""
    text = content.strip()
    if not text:
        return False
    if text.startswith("---\n") and "\n---" in text:
        return True
    if re.search(r"(?m)^\s*-\s+\[[^\]]+\]\s+\S", text):
        return True
    return re.search(r"(?m)^\s*[A-Za-z][\w \-]{1,40}:\s+\S+", text) is not None and "\n" in text


def has_frontmatter_kind_marker(content: str, *names: str) -> bool:
    """Return whether frontmatter explicitly declares one of the named kinds."""
    markers = {normalize_kind_marker(name) for name in names}
    fields = extract_frontmatter_fields(content)
    for key in ("kind", "type", "artifact", "artifact_kind", "output_kind"):
        value = normalize_kind_marker(fields.get(key, ""))
        if value in markers:
            return True
    return False


def looks_like_named_artifact(content: str, *names: str) -> bool:
    """Return whether the content declares one of the named artifact headings."""
    text = content.strip()
    if not text:
        return False
    match = re.search(r"(?im)^#{1,6}\s+(?P<heading>[A-Za-z][A-Za-z _\-]{0,80})$", text)
    if match is None:
        return False
    heading = normalize_kind_marker(match.group("heading"))
    markers = {normalize_kind_marker(name) for name in names}
    return heading in markers


def looks_like_timeline_artifact(content: str) -> bool:
    """Return whether the content is a timeline-like artifact body."""
    text = content.strip()
    if not text:
        return False
    if looks_like_named_artifact(text, "timeline", "event timeline"):
        return True
    if has_frontmatter_kind_marker(text, "timeline", "event_timeline"):
        return True
    return False


def looks_like_root_cause_candidate(content: str) -> bool:
    """Return whether the content is a root-cause-candidate style artifact body."""
    text = content.strip()
    if not text:
        return False
    if looks_like_named_artifact(text, "root cause candidate"):
        return True
    if has_frontmatter_kind_marker(text, "root_cause_candidate", "root cause candidate"):
        return True
    return False


def infer_structured_artifact_kind_from_context(user_content: str) -> str | None:
    """Infer an artifact kind from the user's request when the body is structured but unnamed."""
    lowered = user_content.lower()
    if any(token in lowered for token in ("inspection", "inspect", "检查", "巡检")):
        return OUTPUT_KIND_INSPECTION_ARTIFACT
    if any(token in lowered for token in ("report", "报告", "汇报")):
        return OUTPUT_KIND_REPORT_ARTIFACT
    if any(token in lowered for token in ("case", "工单", "案件")):
        return OUTPUT_KIND_CASE_ARTIFACT
    if any(token in lowered for token in ("timeline", "时间线", "时序")):
        return OUTPUT_KIND_TIMELINE_ARTIFACT
    if any(token in lowered for token in ("root cause candidate", "root-cause candidate", "根因候选")):
        return OUTPUT_KIND_ROOT_CAUSE_CANDIDATE
    return None


def classify_output_kind(
    *,
    user_content: str,
    final_content: str | None,
    messages: list[dict[str, Any]] | None = None,
) -> str:
    """Classify the final output into a stable lightweight kind label."""
    del messages  # Reserved for future evidence-aware classification refinements.
    text = (final_content or "").strip()
    if not text:
        return OUTPUT_KIND_GENERIC_REPLY
    if looks_like_timeline_artifact(text):
        return OUTPUT_KIND_TIMELINE_ARTIFACT
    if looks_like_root_cause_candidate(text):
        return OUTPUT_KIND_ROOT_CAUSE_CANDIDATE
    if looks_like_named_artifact(text, "inspection"):
        return OUTPUT_KIND_INSPECTION_ARTIFACT
    if looks_like_named_artifact(text, "report"):
        return OUTPUT_KIND_REPORT_ARTIFACT
    if looks_like_named_artifact(text, "case"):
        return OUTPUT_KIND_CASE_ARTIFACT
    if workflow_control.looks_like_troubleshooting_content(user_content) and (
        workflow_control.looks_like_troubleshooting_content(text)
        or any(phrase in text for phrase in ("当前倾向", "根因已确认", "问题已经定位到", "可以确定就是"))
    ):
        return OUTPUT_KIND_TROUBLESHOOTING_REPLY
    if looks_like_generic_structured_body(text):
        if has_frontmatter_kind_marker(text, "inspection"):
            return OUTPUT_KIND_INSPECTION_ARTIFACT
        if has_frontmatter_kind_marker(text, "report"):
            return OUTPUT_KIND_REPORT_ARTIFACT
        if has_frontmatter_kind_marker(text, "case"):
            return OUTPUT_KIND_CASE_ARTIFACT
        if has_frontmatter_kind_marker(text, "timeline", "event_timeline"):
            return OUTPUT_KIND_TIMELINE_ARTIFACT
        if has_frontmatter_kind_marker(text, "root_cause_candidate", "root cause candidate"):
            return OUTPUT_KIND_ROOT_CAUSE_CANDIDATE
        if inferred_kind := infer_structured_artifact_kind_from_context(user_content):
            return inferred_kind
    return OUTPUT_KIND_GENERIC_REPLY


def split_troubleshooting_evidence_and_conclusion(content: str) -> tuple[str, str | None, str]:
    """Split a reply into evidence text, a downgraded tendency phrase, and trailing content."""
    patterns: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"根因已确认[，,]*(?:就是|是)(?P<target>[^。！？\n，,;；]+)"), "现有证据更偏向{target}"),
        (re.compile(r"问题已经定位到(?P<target>[^。！？\n，,;；]+)"), "问题更集中在{target}"),
        (re.compile(r"可以确定(?:就是|是)(?P<target>[^。！？\n，,;；]+)"), "现有证据更偏向{target}"),
    )
    earliest: tuple[int, int, re.Match[str], str] | None = None
    for pattern, template in patterns:
        match = pattern.search(content)
        if match is None:
            continue
        candidate = (match.start(), match.end(), match, template)
        if earliest is None or candidate[0] < earliest[0]:
            earliest = candidate
    if earliest is None:
        return content.strip(), None, ""

    start, end, match, template = earliest
    evidence = content[:start].rstrip("，,。；; \n")
    suffix = content[end:].lstrip("，,。；; \n")
    target = str(match.groupdict().get("target", "")).strip("，,。；; \n")
    tendency = template.format(target=target)
    if tendency and not tendency.endswith("。"):
        tendency = tendency + "。"
    return evidence, tendency, suffix


def count_evidence_signals(content: str) -> int:
    """Count coarse evidence-bearing segments to decide whether a tendency is justified."""
    signals = 0
    for chunk in re.split(r"[。\n！？!?；;]+", content):
        token = chunk.strip()
        if not token:
            continue
        if any(marker in token for marker in ("已确认事实", "关键证据", "事实", "证据")):
            signals += 1
            continue
        if any(marker in token for marker in ("日志", "报错", "错误", "异常", "超时", "失败", "卡住", "告警", "堆栈", "服务状态", "进程状态", "磁盘状态", "网络状态", "对比", "检查", "看到", "发现", "显示")):
            signals += 1
    return signals


def rewrite_remaining_strong_conclusions(content: str) -> str:
    """Remove any remaining strong-conclusion phrases inside preserved body text."""
    patterns: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"根因已确认[，,]*(?:就是|是)(?P<target>[^。！？\n，,;；]+)"), "现有证据更偏向{target}"),
        (re.compile(r"问题已经定位到(?P<target>[^。！？\n，,;；]+)"), "问题更集中在{target}"),
        (re.compile(r"可以确定(?:就是|是)(?P<target>[^。！？\n，,;；]+)"), "现有证据更偏向{target}"),
    )

    rewritten = content
    for pattern, _template in patterns:
        rewritten = pattern.sub("", rewritten)
    rewritten = re.sub(r"(^|[\n])[\s，,。；;]+", r"\1", rewritten)
    return rewritten


def summarize_tool_evidence(messages: list[dict[str, Any]] | None) -> str | None:
    """Build a minimal visible evidence line from current-turn tool results when needed."""
    if not messages:
        return None
    for message in messages:
        if message.get("role") != "tool":
            continue
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        summary = re.split(r"[\n。！？!?]", content, maxsplit=1)[0].strip()
        if summary:
            return f"已确认事实：本轮只读调查拿到了证据输出，例如 {summary[:80]}。"
        return "已确认事实：本轮只读调查拿到了证据输出。"
    return None


def ensure_minimal_uncertainty_and_next_step(content: str) -> str:
    """Append minimal uncertainty and next-step lines if they are missing."""
    lines = [line.rstrip() for line in content.strip().splitlines() if line.strip()]
    combined = "\n".join(lines)
    if not any(marker in combined for marker in ("不确定", "仍需", "还需要", "还要", "未确认", "风险", "待验证")):
        lines.append("不确定点：还需要再核对一轮只读证据。")
    if not any(marker in combined for marker in ("下一步", "建议", "验证", "先核对", "再确认", "继续检查")):
        lines.append("下一步：建议先补一条最能验证当前判断的只读检查。")
    return "\n".join(lines)


def is_troubleshooting_result_candidate(content: str) -> bool:
    """Return whether a troubleshooting reply should be reshaped in evidence-first mode."""
    if not content.strip():
        return False
    if looks_like_structured_artifact_body(content):
        return False
    return workflow_control.looks_like_troubleshooting_content(content) or any(
        phrase in content for phrase in ("当前倾向", "根因已确认", "问题已经定位到", "可以确定就是")
    )


def shape_evidence_first_result(
    *,
    session: Session | None,
    user_content: str,
    final_content: str | None,
    messages: list[dict[str, Any]] | None = None,
) -> str | None:
    """Boundedly reshape troubleshooting conclusions when evidence-first mode is active."""
    if final_content is None or session is None:
        return final_content
    if session.metadata.get("workflow_result_mode") != "evidence_first":
        return final_content
    if not workflow_control.looks_like_troubleshooting_content(user_content):
        return final_content
    if not is_troubleshooting_result_candidate(final_content):
        return final_content

    evidence_text, tendency_text, suffix_text = split_troubleshooting_evidence_and_conclusion(final_content)
    sections = [part.strip() for part in (evidence_text, suffix_text) if part.strip()]
    if not sections and tendency_text:
        if tool_summary := summarize_tool_evidence(messages):
            sections.append(tool_summary)
    body = rewrite_remaining_strong_conclusions("\n".join(sections).strip())
    evidence_signals = count_evidence_signals(body)
    has_explicit_evidence_labels = any(marker in body for marker in ("已确认事实", "关键证据"))

    if tendency_text:
        if body and (evidence_signals >= 2 or has_explicit_evidence_labels):
            body = f"{body}\n当前倾向：{tendency_text}"
        elif not body:
            tool_summary = summarize_tool_evidence(messages)
            if tool_summary:
                body = f"{tool_summary}\n当前倾向：{tendency_text}"
            else:
                body = "证据缺口：当前回复未展开可核对证据。"
    if not body:
        body = final_content.strip()
    return ensure_minimal_uncertainty_and_next_step(body)
