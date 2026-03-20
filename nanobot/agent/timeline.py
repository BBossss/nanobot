"""Minimal log timeline extraction and rendering."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

_TIMESTAMP_PATTERNS = (
    re.compile(r"(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"),
    re.compile(r"(?P<ts>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"),
)
_HEADER_PATTERNS = (
    re.compile(r"^\[target=[^\]]+\]\s+tail\s+\d+\s+lines\s+from\s+.+:$"),
    re.compile(r"^\[target=[^\]]+\]\s+Found(?:\s+\d+\s+match\(es\))?\s+in\s+.+:$"),
    re.compile(r"^\[target=[^\]]+\]\s+Found matches in\s+.+:$"),
)
_NEAR_EVENT_SECONDS = 5


@dataclass(frozen=True)
class TimelineArtifactEvent:
    timestamp_normalized: str
    timestamp_raw: str
    event: str
    evidence: str
    target: str | None = None
    source: str | None = None
    scope: str | None = None


@dataclass(frozen=True)
class TimelineArtifact:
    events: list[TimelineArtifactEvent]
    incident: str | None = None
    target: str | None = None
    window_start: str | None = None
    window_end: str | None = None
    coverage_note: str | None = None


@dataclass(frozen=True)
class LogTimelineEvent:
    target_id: str
    tool_name: str
    event_time: datetime | None
    observed_at: datetime
    raw_line: str
    normalized_message: str
    time_status: str


@dataclass(frozen=True)
class CrossTargetTimelineInput:
    tool_name: str
    results: list[dict[str, object]]


def extract_log_events(
    *,
    target_id: str,
    tool_name: str,
    content: str,
    observed_at: datetime,
) -> list[LogTimelineEvent]:
    """Extract timeline events from a log tool result string."""
    events: list[LogTimelineEvent] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or _is_header_line(line):
            continue
        event_time = _parse_timestamp(line)
        normalized = _normalize_message(line)
        events.append(
            LogTimelineEvent(
                target_id=target_id,
                tool_name=tool_name,
                event_time=event_time,
                observed_at=observed_at,
                raw_line=line,
                normalized_message=normalized,
                time_status="parsed" if event_time else "unknown",
            )
        )
    return events


def build_log_timeline(events: list[LogTimelineEvent]) -> str:
    """Render a minimal timeline summary from extracted log events."""
    parsed = sorted(
        [event for event in events if event.time_status == "parsed" and event.event_time is not None],
        key=lambda event: (event.event_time, event.target_id, event.raw_line),
    )
    unknown = [event for event in events if event.time_status != "parsed"]
    sections: list[str] = []

    if parsed:
        sections.append("## Timeline")
        for event in parsed:
            sections.append(
                f"- {event.event_time.strftime('%H:%M:%S')} {event.target_id} {event.normalized_message}"
            )
        near = _group_near_events(parsed)
        if near:
            sections.append("")
            sections.append("## Concurrent / Near Events")
            sections.extend(near)

    if unknown:
        if sections:
            sections.append("")
        sections.append("## No Timestamp Evidence")
        for event in unknown:
            sections.append(f"- {event.target_id}: {event.raw_line}")

    return "\n".join(sections)


def build_cross_target_timeline_artifact(
    events: list[LogTimelineEvent] | None = None,
    *,
    tool_name: str | None = None,
    results: list[dict[str, Any]] | None = None,
    incident: str | None = None,
    target_scope: str | None = None,
) -> TimelineArtifact:
    """Build a cross-target timeline artifact from log evidence."""
    if results is not None:
        if tool_name is None:
            raise ValueError("tool_name is required when building from multi-target results")
        return _build_cross_target_timeline_artifact_from_results(
            tool_name=tool_name,
            results=results,
            incident=incident,
            target_scope=target_scope,
        )
    if events is None:
        events = []
    return _build_cross_target_timeline_artifact_from_events(
        events=events,
        incident=incident,
        target_scope=target_scope,
    )


def _build_cross_target_timeline_artifact_from_results(
    *,
    tool_name: str,
    results: list[dict[str, Any]],
    incident: str | None,
    target_scope: str | None,
) -> TimelineArtifact:
    parsed_events: list[LogTimelineEvent] = []
    for result in results:
        if str(result.get("status", "ok")) != "ok":
            continue
        target_id = str(result.get("target_id", "unknown"))
        content = str(result.get("content", ""))
        observed_at = result.get("observed_at")
        if not isinstance(observed_at, datetime):
            observed_at = datetime.now()
        parsed_events.extend(
            event
            for event in extract_log_events(
                target_id=target_id,
                tool_name=tool_name,
                content=content,
                observed_at=observed_at,
            )
            if event.time_status == "parsed" and event.event_time is not None
        )
    return _build_cross_target_timeline_artifact_core(
        parsed_events=parsed_events,
        incident=incident,
        target_scope=target_scope,
    )


def _build_cross_target_timeline_artifact_from_events(
    *,
    events: list[LogTimelineEvent],
    incident: str | None,
    target_scope: str | None,
) -> TimelineArtifact:
    return _build_cross_target_timeline_artifact_core(
        parsed_events=[event for event in events if event.time_status == "parsed" and event.event_time is not None],
        incident=incident,
        target_scope=target_scope,
    )


def _build_cross_target_timeline_artifact_core(
    *,
    parsed_events: list[LogTimelineEvent],
    incident: str | None,
    target_scope: str | None,
) -> TimelineArtifact:
    coverage_note = "Only evidence with explicit timestamps is included in this timeline."
    if not parsed_events:
        return TimelineArtifact(
            incident=incident,
            target=target_scope,
            window_start=None,
            window_end=None,
            coverage_note=coverage_note,
            events=[],
        )

    sorted_events = sorted(
        parsed_events,
        key=lambda event: (event.event_time or datetime.min, event.target_id, event.raw_line),
    )
    source_order = {id(event): index for index, event in enumerate(parsed_events)}
    clusters = _cluster_cross_target_log_events(sorted_events)
    cross_target_events: list[TimelineArtifactEvent] = []

    for cluster in clusters:
        cross_target_events.append(
            _render_cross_target_event(cluster, source_order=source_order)
        )

    window_start = min(event.event_time for event in sorted_events if event.event_time is not None)
    window_end = max(event.event_time for event in sorted_events if event.event_time is not None)
    target = target_scope or ",".join(dict.fromkeys(event.target_id for event in sorted_events))

    return TimelineArtifact(
        incident=incident,
        target=target,
        window_start=window_start.isoformat(timespec="seconds") if window_start else None,
        window_end=window_end.isoformat(timespec="seconds") if window_end else None,
        coverage_note=coverage_note,
        events=cross_target_events,
    )


def _cluster_cross_target_log_events(events: list[LogTimelineEvent]) -> list[list[LogTimelineEvent]]:
    grouped: dict[str, list[LogTimelineEvent]] = {}
    for event in events:
        grouped.setdefault(event.normalized_message, []).append(event)

    clusters: list[list[LogTimelineEvent]] = []
    for normalized_message in sorted(
        grouped,
        key=lambda key: (
            grouped[key][0].event_time or datetime.min,
            grouped[key][0].target_id,
            key,
        ),
    ):
        message_events = sorted(
            grouped[normalized_message],
            key=lambda event: (event.event_time or datetime.min, event.target_id, event.raw_line),
        )
        current_cluster: list[LogTimelineEvent] = []
        for event in message_events:
            if not current_cluster:
                current_cluster = [event]
                continue
            cluster_end = current_cluster[-1].event_time
            if (
                cluster_end is not None
                and event.event_time is not None
                and (event.event_time - cluster_end).total_seconds() <= _NEAR_EVENT_SECONDS
            ):
                current_cluster.append(event)
            else:
                clusters.append(current_cluster)
                current_cluster = [event]
        if current_cluster:
            clusters.append(current_cluster)

    return sorted(
        clusters,
        key=lambda cluster: (
            cluster[0].event_time or datetime.min,
            cluster[0].target_id,
            cluster[0].normalized_message,
        ),
    )


def _render_cross_target_event(
    cluster: list[LogTimelineEvent],
    *,
    source_order: dict[int, int],
) -> TimelineArtifactEvent:
    cluster_sorted = sorted(cluster, key=lambda event: (event.event_time or datetime.min, event.target_id, event.raw_line))
    event_time = cluster_sorted[0].event_time
    if event_time is None:
        raise ValueError("cross-target timeline events require timestamps")
    timestamp_normalized = event_time.isoformat(timespec="seconds")
    timestamp_raw = _extract_timestamp_text(cluster_sorted[0].raw_line) or cluster_sorted[0].raw_line
    targets = [event.target_id for event in cluster_sorted]
    sources = [
        event.tool_name
        for event in sorted(cluster_sorted, key=lambda event: (source_order.get(id(event), 0), event.target_id, event.raw_line))
    ]
    evidence = " | ".join(event.raw_line for event in cluster_sorted)
    scope = _scope_for_cross_target_cluster(cluster_sorted)
    event_text = f"{scope} {cluster_sorted[0].normalized_message} appeared on {', '.join(targets)}"
    target = ",".join(dict.fromkeys(targets))
    source = ",".join(dict.fromkeys(sources))

    return TimelineArtifactEvent(
        timestamp_normalized=timestamp_normalized,
        timestamp_raw=timestamp_raw,
        event=event_text,
        evidence=evidence,
        target=target,
        source=source,
        scope=scope,
    )


def _scope_for_cross_target_cluster(cluster: list[LogTimelineEvent]) -> str:
    distinct_targets = {event.target_id for event in cluster}
    if len(distinct_targets) == 1:
        return "local"
    timestamps = {event.event_time for event in cluster if event.event_time is not None}
    if len(timestamps) == 1:
        return "shared"
    return "near_shared"


def _extract_timestamp_text(line: str) -> str | None:
    for pattern in _TIMESTAMP_PATTERNS:
        match = pattern.search(line)
        if match is not None:
            return match.group("ts")
    return None


def format_timeline_artifact(artifact: TimelineArtifact) -> str:
    """Render a stable incident timeline artifact as Markdown."""
    if not artifact.events:
        raise ValueError("timeline artifacts must contain at least one event")
    for event in artifact.events:
        _validate_timeline_artifact_event(event)
    lines: list[str] = ["# Timeline"]
    if artifact.incident:
        lines.append("")
        lines.append(f"Incident: {artifact.incident}")
    if artifact.target:
        lines.append(f"Target: {artifact.target}")
    if artifact.window_start and artifact.window_end:
        lines.append(f"Window: {artifact.window_start} to {artifact.window_end}")
    elif artifact.window_start:
        lines.append(f"Window start: {artifact.window_start}")
    elif artifact.window_end:
        lines.append(f"Window end: {artifact.window_end}")

    lines.append("")
    lines.append("## Events")
    for event in artifact.events:
        lines.append("")
        lines.append(f"- Timestamp: {event.timestamp_normalized}")
        lines.append(f"  Event: {event.event}")
        lines.append(f"  Evidence: {event.evidence}")
        if event.target:
            lines.append(f"  Target: {event.target}")
        if event.source:
            lines.append(f"  Source: {event.source}")

    if artifact.coverage_note:
        lines.append("")
        lines.append("## Coverage Note")
        lines.append("")
        lines.append(artifact.coverage_note)

    return "\n".join(lines).rstrip()


def _validate_timeline_artifact_event(event: TimelineArtifactEvent) -> None:
    if not event.timestamp_normalized.strip():
        raise ValueError("timeline artifact event requires timestamp_normalized")
    if not event.timestamp_raw.strip():
        raise ValueError("timeline artifact event requires timestamp_raw")
    if not event.event.strip():
        raise ValueError("timeline artifact event requires event")
    if not event.evidence.strip():
        raise ValueError("timeline artifact event requires evidence")
    if event.scope is not None and event.scope not in {"shared", "near_shared", "local"}:
        raise ValueError("timeline artifact event requires a valid scope")


def _parse_timestamp(line: str) -> datetime | None:
    for pattern in _TIMESTAMP_PATTERNS:
        match = pattern.search(line)
        if not match:
            continue
        ts = match.group("ts")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(ts, fmt)
            except ValueError:
                continue
    return None


def _normalize_message(line: str) -> str:
    message = line
    for pattern in _TIMESTAMP_PATTERNS:
        message = pattern.sub("", message, count=1).strip()
    message = re.sub(r"^\d+:\s*", "", message)
    return message or line.strip()


def _is_header_line(line: str) -> bool:
    return any(pattern.match(line) for pattern in _HEADER_PATTERNS)


def _group_near_events(events: list[LogTimelineEvent]) -> list[str]:
    lines: list[str] = []
    used: set[int] = set()
    for idx, event in enumerate(events):
        if idx in used:
            continue
        if event.event_time is None:
            continue
        group = [event]
        for other_idx in range(idx + 1, len(events)):
            other = events[other_idx]
            if other.event_time is None:
                continue
            delta = abs((other.event_time - event.event_time).total_seconds())
            if delta <= _NEAR_EVENT_SECONDS and other.normalized_message == event.normalized_message:
                used.add(other_idx)
                group.append(other)
        if len(group) > 1:
            targets = ", ".join(item.target_id for item in group)
            lines.append(f"- {targets}: {event.normalized_message}")
    return lines
