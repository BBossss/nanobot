"""Investigation feedback rendering helpers."""

from __future__ import annotations

from typing import Any, Protocol


class InvestigationLike(Protocol):
    visited_buckets: list[str]
    multi_target_active: bool


def render_progress_reason(
    bucket: str,
    *,
    previous_bucket: str | None,
    multi_target_total: int,
) -> str | None:
    if multi_target_total > 1:
        return render_multi_target_reason(bucket)
    if previous_bucket == bucket:
        return None
    reason_map = {
        "log": "为了先确认最近的异常线索，所以先读取日志，判断问题更像报错、超时还是依赖异常。",
        "service": "刚才已经看到可疑线索，所以再检查服务状态，判断是服务本身异常还是外部依赖问题。",
        "process": "刚才线索还不够完整，所以再检查进程状态，确认是否存在退出、卡住或异常重启。",
        "disk": "当前怀疑底层资源异常，所以先检查磁盘状态，判断是否存在容量或 I/O 问题。",
        "network": "当前怀疑连通性问题，所以先检查网络状态，判断是否存在链路或端口异常。",
        "other": "先补一条只读调查，确认当前最可疑的方向。",
    }
    prefix = "所以先" if previous_bucket is None else "所以再"
    text = reason_map.get(bucket, reason_map["other"])
    if previous_bucket is None:
        return text.replace("所以先", prefix, 1) if text.startswith("所以先") else text
    replacements = {
        "所以先读取日志": f"{prefix}读取日志",
        "所以再检查服务状态": f"{prefix}检查服务状态",
        "所以再检查进程状态": f"{prefix}检查进程状态",
        "所以先检查磁盘状态": f"{prefix}检查磁盘状态",
        "所以先检查网络状态": f"{prefix}检查网络状态",
    }
    for src, dst in replacements.items():
        if src in text:
            return text.replace(src, dst, 1)
    return text


def render_multi_target_reason(bucket: str) -> str:
    reason_map = {
        "service": "这一步需要区分共性异常还是局部异常，所以先在多节点间对比服务状态。",
        "log": "当前怀疑多个节点共享同一类报错，所以先在多节点间对比日志线索。",
        "process": "为了判断是否是局部节点卡住，所以先在多节点间对比进程状态。",
        "disk": "为了判断是否是底层资源共性问题，所以先在多节点间对比磁盘状态。",
        "network": "为了判断是否是共享链路问题，所以先在多节点间对比网络状态。",
        "other": "为了比较节点间差异，所以先在多节点间执行只读调查。",
    }
    return reason_map.get(bucket, reason_map["other"])


def render_progress_action(name: str, arguments: dict[str, Any], *, multi_target_total: int) -> str:
    arg_value = (
        arguments.get("service")
        or arguments.get("path")
        or arguments.get("pattern")
        or arguments.get("keyword")
        or arguments.get("unit")
    )
    suffix = f"：{name}({arg_value})" if arg_value else f"：{name}"
    if name in {"read_log_tail", "search_log", "find_logs", "journal_tail"}:
        prefix = "正在读取日志"
    elif name == "service_status":
        prefix = "正在检查服务状态"
    elif name == "process_snapshot":
        prefix = "正在检查进程状态"
    elif name == "disk_snapshot":
        prefix = "正在检查磁盘状态"
    elif name == "network_snapshot":
        prefix = "正在检查网络状态"
    else:
        prefix = "正在执行只读调查"
    if multi_target_total > 1:
        return f"正在对多节点执行只读检查（{multi_target_total} 个目标）{suffix}"
    return f"{prefix}{suffix}"


def render_progress_heartbeat(name: str, *, multi_target_total: int) -> str:
    if multi_target_total > 1:
        return "仍在多节点检查中，请稍等。"
    if name in {"read_log_tail", "search_log", "find_logs", "journal_tail"}:
        return "仍在读取日志，请稍等。"
    if name == "service_status":
        return "仍在检查服务状态，请稍等。"
    if name == "process_snapshot":
        return "仍在检查进程状态，请稍等。"
    if name == "disk_snapshot":
        return "仍在检查磁盘状态，请稍等。"
    if name == "network_snapshot":
        return "仍在检查网络状态，请稍等。"
    return "仍在执行只读调查，请稍等。"


def render_progress_summary(investigation: InvestigationLike) -> str | None:
    if not investigation.visited_buckets:
        return None
    labels = {
        "log": "日志",
        "service": "服务状态",
        "process": "进程状态",
        "disk": "磁盘状态",
        "network": "网络状态",
        "other": "只读调查",
    }
    ordered = [labels.get(bucket, "只读调查") for bucket in investigation.visited_buckets]
    if investigation.multi_target_active:
        if ordered:
            return f"刚才先检查了多节点{ordered[0]}，再汇总节点间差异；下面给出当前判断。"
        return "刚才先做了多节点对比调查；下面给出当前判断。"
    if len(ordered) == 1:
        return f"刚才先检查了{ordered[0]}；下面给出当前判断。"
    return f"刚才先检查了{ordered[0]}，再检查了{ordered[1]}；下面给出当前判断。"
