"""Skill routing policy for HCI-specific contextual skill injection."""

from __future__ import annotations

from collections.abc import Iterable


CASE_SUMMARY_MARKERS = (
    "生成案例摘要",
    "案例摘要",
    "整理为案例",
    "保存案例",
    "保存摘要",
    "归档案例",
    "总结并保存",
    "case summary",
    "save case",
)

INSPECTION_MARKERS = (
    "inspection:run",
    "巡检",
    "巡检结果",
    "巡检报告",
    "分析巡检",
    "inspection report",
    "inspection result",
)

STORAGE_NETWORK_KEYWORDS = (
    "存储",
    "磁盘",
    "副本",
    "ceph",
    "volume",
    "io",
    "i/o",
    "latency",
    "timeout",
    "网络",
    "丢包",
    "mtu",
    "bond",
    "vlan",
    "ovs",
    "bridge",
    "node health",
    "cpu高",
    "load高",
)

SPECIALTY_TAGS = {
    "storage",
    "network",
    "node",
    "node-health",
    "disk",
    "io",
}


class SkillRoutingPolicy:
    """Select contextual HCI skills for one request."""

    BASE_SKILL = "hci-troubleshooting"

    @classmethod
    def select_skills(
        cls,
        *,
        content: str,
        channel: str | None = None,
        metadata: dict | None = None,
    ) -> list[str]:
        text = (content or "").strip()
        lower = text.lower()
        meta = metadata or {}
        selected: list[str] = [cls.BASE_SKILL]

        if cls._is_case_summary(lower, meta):
            selected.append("hci-case-summary")

        if cls._is_inspection(lower, channel, meta):
            selected.append("hci-inspection-analysis")

        if cls._is_storage_network(lower, meta):
            selected.append("hci-storage-network-sop")

        return cls._dedupe(selected)

    @staticmethod
    def _dedupe(names: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for name in names:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
        return ordered

    @staticmethod
    def _is_case_summary(lower: str, metadata: dict) -> bool:
        if any(marker in lower for marker in CASE_SUMMARY_MARKERS):
            return True
        phase = str(metadata.get("phase", "")).lower()
        return phase in {"case_summary", "case_record", "case_save"}

    @staticmethod
    def _is_inspection(lower: str, channel: str | None, metadata: dict) -> bool:
        if any(marker in lower for marker in INSPECTION_MARKERS):
            return True
        if channel == "system" and lower.startswith("inspection:run"):
            return True
        phase = str(metadata.get("phase", "")).lower()
        if phase in {"inspection", "inspection_analysis", "inspection_report"}:
            return True
        trigger = str(metadata.get("trigger", "")).lower()
        return trigger.startswith("inspection")

    @staticmethod
    def _is_storage_network(lower: str, metadata: dict) -> bool:
        if any(keyword in lower for keyword in STORAGE_NETWORK_KEYWORDS):
            return True
        tags = metadata.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        lowered_tags = {str(tag).lower() for tag in tags}
        return bool(lowered_tags & SPECIALTY_TAGS)
