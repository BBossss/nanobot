"""Minimal log timeline extraction and rendering."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

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
