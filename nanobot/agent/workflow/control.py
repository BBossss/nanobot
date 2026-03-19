"""Troubleshooting workflow control helpers."""

from __future__ import annotations

import re

from nanobot.session.manager import Session

CONTROL_BOUNDARY_CHARS = {"，", ",", "。", "；", ";", "：", ":", "、", "！", "!", "？", "?"}
TROUBLESHOOTING_CONTROL_PHRASES: tuple[tuple[str, str], ...] = (
    ("暂停", "pause"),
    ("继续", "resume"),
    ("只查日志", "change_focus"),
    ("先只看日志", "change_focus"),
    ("不要多节点", "narrow_scope"),
    ("先别扩到多节点", "narrow_scope"),
)
RESULT_MODE_ENABLE_PHRASES: tuple[str, ...] = (
    "先别急着下结论",
    "先给证据再说判断",
    "先别定性",
    "先证据后判断",
)
RESULT_MODE_DISABLE_PHRASES: tuple[str, ...] = (
    "直接说结论",
    "你可以下判断了",
    "直接给判断",
)


def normalized_reply_token(content: str) -> str:
    return re.sub(r"\s+", "", content.strip().lower())


def contains_bounded_phrase(token: str, phrase: str) -> bool:
    """Return whether a bounded control phrase appears at the start of a turn."""
    if token == phrase:
        return True
    if not token.startswith(phrase):
        return False
    if len(token) == len(phrase):
        return True
    return token[len(phrase)] in CONTROL_BOUNDARY_CHARS


def contains_bounded_phrase_anywhere(token: str, phrase: str) -> bool:
    """Return whether a control phrase appears as a punctuation-bounded segment."""
    start = token.find(phrase)
    while start != -1:
        before_ok = start == 0 or token[start - 1] in CONTROL_BOUNDARY_CHARS
        end = start + len(phrase)
        after_ok = end == len(token) or token[end] in CONTROL_BOUNDARY_CHARS
        if before_ok and after_ok:
            return True
        start = token.find(phrase, start + 1)
    return False


def looks_like_troubleshooting_content(content: str) -> bool:
    """Return whether the current turn looks like troubleshooting context."""
    token = normalized_reply_token(content)
    strong_markers = (
        "出问题",
        "报错",
        "异常",
        "故障",
        "崩溃",
        "卡住",
        "超时",
        "延迟",
        "服务状态",
        "排查",
        "调查",
        "诊断",
        "告警",
    )
    if any(marker in token for marker in strong_markers):
        return True
    resource_nouns = ("网络", "节点", "集群", "进程", "磁盘")
    if any(noun in token for noun in resource_nouns):
        resource_cues = (
            "状态",
            "异常",
            "故障",
            "报错",
            "告警",
            "超时",
            "崩溃",
            "卡住",
            "恢复",
            "排查",
            "调查",
            "诊断",
            "检查",
            "看",
            "查",
            "对比",
            "快照",
            "不通",
            "丢包",
            "连接不上",
            "启动失败",
        )
        return any(cue in token for cue in resource_cues)
    if "日志" in token:
        log_cues = (
            "排查",
            "调查",
            "诊断",
            "报错",
            "异常",
            "故障",
            "告警",
            "超时",
            "崩溃",
            "卡住",
            "错误",
            "恢复",
            "看日志",
            "查日志",
            "读日志",
        )
        return any(cue in token for cue in log_cues)
    return False


def parse_troubleshooting_control_intent(content: str) -> str | None:
    """Map a bounded troubleshooting control phrase to an internal intent."""
    token = normalized_reply_token(content)
    for phrase, intent in TROUBLESHOOTING_CONTROL_PHRASES:
        if contains_bounded_phrase_anywhere(token, phrase):
            return intent
    return None


def parse_result_mode_control_intent(content: str) -> str | None:
    """Map a bounded evidence-first phrase to an internal intent."""
    token = normalized_reply_token(content)
    if any(contains_bounded_phrase(token, phrase) for phrase in RESULT_MODE_ENABLE_PHRASES):
        return "evidence_first_enable"
    if any(contains_bounded_phrase(token, phrase) for phrase in RESULT_MODE_DISABLE_PHRASES):
        return "evidence_first_disable"
    return None


def strip_trailing_control_punctuation(token: str) -> str:
    """Remove trailing punctuation so standalone control turns can stay bounded."""
    return token.rstrip("，,。；;：:、！!？?")


def is_standalone_result_mode_control(content: str) -> bool:
    """Return whether the current turn is only a result-mode control phrase."""
    token = normalized_reply_token(content)
    return strip_trailing_control_punctuation(token) in {
        *RESULT_MODE_ENABLE_PHRASES,
        *RESULT_MODE_DISABLE_PHRASES,
    }


def latest_user_turn_was_troubleshooting(session: Session) -> bool:
    """Return whether the immediately preceding user turn was troubleshooting-like."""
    for message in reversed(session.get_history(max_messages=12)):
        if message.get("role") != "user":
            continue
        content = str(message.get("content") or "")
        return looks_like_troubleshooting_content(content)
    return False


def latest_assistant_turn_requests_continue_confirmation(session: Session) -> bool:
    """Return whether the last assistant turn asked the user to confirm whether to continue."""
    for message in reversed(session.get_history(max_messages=12)):
        if message.get("role") != "assistant":
            continue
        content = str(message.get("content") or "").strip()
        return "请确认是否继续" in content
    return False


def should_consider_result_mode_control(session: Session, content: str) -> bool:
    """Return whether result-mode control parsing is allowed for this turn."""
    if looks_like_troubleshooting_content(content):
        return True
    if not is_standalone_result_mode_control(content):
        return False
    if session.metadata.get("workflow_result_mode") == "evidence_first":
        return True
    if session.metadata.get("workflow_paused") is True:
        return True
    if session.metadata.get("pending_target_resolution") is not None:
        return True
    if session.metadata.get("workflow_focus_hint"):
        return True
    if session.metadata.get("workflow_scope_constraints"):
        return True
    if session.metadata.get("expansion_confirmed") is True:
        return True
    return latest_user_turn_was_troubleshooting(session)


def handle_workflow_control(session: Session, content: str, *, clear_confirmed_target_scope) -> str | None:
    """Persist bounded workflow control state and return a short acknowledgement."""
    if session.metadata.pop("workflow_skip_control_once", False):
        return None

    intent = parse_troubleshooting_control_intent(content)
    if intent == "resume" and latest_assistant_turn_requests_continue_confirmation(session):
        intent = None
    if intent is None and should_consider_result_mode_control(session, content):
        intent = parse_result_mode_control_intent(content)
    if intent is None:
        return None

    session.metadata["workflow_last_control_input"] = content.strip()

    if intent == "pause":
        session.metadata["workflow_paused"] = True
        return "已暂停当前排查；如需继续，请回复“继续”。"
    if intent == "resume":
        session.metadata["workflow_paused"] = False
        return "已继续当前排查。"
    if intent == "change_focus":
        session.metadata["workflow_focus_hint"] = "logs_only"
        return "后续先按日志方向继续调查。"
    if intent == "narrow_scope":
        session.metadata["workflow_scope_constraints"] = {"forbid_multi_target": True}
        session.metadata["pending_target_resolution"] = None
        clear_confirmed_target_scope(session, skip_reprompt_once=False)
        return "后续保持单节点模式，不扩到多节点。"
    if intent == "evidence_first_enable":
        session.metadata["workflow_result_mode"] = "evidence_first"
        session.metadata["workflow_result_mode_reason"] = content.strip()
        return "后续先按证据收口；如果判断还不够稳，我会先列证据和未确认点。"
    if intent == "evidence_first_disable":
        session.metadata.pop("workflow_result_mode", None)
        session.metadata.pop("workflow_result_mode_reason", None)
        return "已解除证据优先收口；后续可直接给出判断。"
    return None
