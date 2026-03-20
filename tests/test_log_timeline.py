from datetime import datetime

from nanobot.agent.timeline import (
    TimelineArtifact,
    TimelineArtifactEvent,
    build_log_timeline,
    build_timeline_artifact_from_log_events,
    extract_log_events,
    format_timeline_artifact,
)


def test_extract_log_events_parses_timestamp() -> None:
    observed_at = datetime(2026, 3, 18, 10, 30, 0)

    events = extract_log_events(
        target_id="node-a",
        tool_name="read_log_tail",
        content=(
            "[target=root@10.0.0.1] tail 2 lines from /sf/log/app.log:\n"
            "2026-03-18 10:21:03 timeout while connecting\n"
            "2026-03-18 10:21:05 retry exceeded"
        ),
        observed_at=observed_at,
    )

    assert len(events) == 2
    assert events[0].time_status == "parsed"
    assert events[0].event_time == datetime(2026, 3, 18, 10, 21, 3)
    assert events[0].normalized_message == "timeout while connecting"
    assert events[0].observed_at == observed_at


def test_extract_log_events_marks_unknown_when_no_timestamp_exists() -> None:
    observed_at = datetime(2026, 3, 18, 10, 30, 0)

    events = extract_log_events(
        target_id="node-a",
        tool_name="search_log",
        content=(
            "[target=root@10.0.0.1] Found 1 match(es) in /sf/log/app.log:\n"
            "12: timeout while connecting"
        ),
        observed_at=observed_at,
    )

    assert len(events) == 1
    assert events[0].time_status == "unknown"
    assert events[0].event_time is None
    assert events[0].raw_line == "12: timeout while connecting"


def test_build_log_timeline_orders_events_across_targets() -> None:
    observed_at = datetime(2026, 3, 18, 10, 30, 0)
    events = []
    events.extend(
        extract_log_events(
            target_id="node-b",
            tool_name="search_log",
            content=(
                "[target=root@10.0.0.2] Found matches in /sf/log/app.log:\n"
                "18: 2026-03-18 10:21:05 timeout while connecting"
            ),
            observed_at=observed_at,
        )
    )
    events.extend(
        extract_log_events(
            target_id="node-a",
            tool_name="read_log_tail",
            content=(
                "[target=root@10.0.0.1] tail 1 lines from /sf/log/app.log:\n"
                "2026-03-18 10:21:03 timeout while connecting"
            ),
            observed_at=observed_at,
        )
    )

    summary = build_log_timeline(events)

    first = summary.index("10:21:03 node-a")
    second = summary.index("10:21:05 node-b")
    assert first < second


def test_build_log_timeline_groups_near_events() -> None:
    observed_at = datetime(2026, 3, 18, 10, 30, 0)
    events = []
    events.extend(
        extract_log_events(
            target_id="node-a",
            tool_name="read_log_tail",
            content=(
                "[target=root@10.0.0.1] tail 1 lines from /sf/log/app.log:\n"
                "2026-03-18 10:21:03 timeout while connecting to storage backend"
            ),
            observed_at=observed_at,
        )
    )
    events.extend(
        extract_log_events(
            target_id="node-b",
            tool_name="search_log",
            content=(
                "[target=root@10.0.0.2] Found matches in /sf/log/app.log:\n"
                "18: 2026-03-18 10:21:05 timeout while connecting to storage backend"
            ),
            observed_at=observed_at,
        )
    )

    summary = build_log_timeline(events)

    assert "Concurrent / Near Events" in summary
    assert "node-a, node-b" in summary


def test_build_log_timeline_lists_unknown_evidence_without_fake_timeline() -> None:
    observed_at = datetime(2026, 3, 18, 10, 30, 0)
    events = extract_log_events(
        target_id="node-a",
        tool_name="search_log",
        content=(
            "[target=root@10.0.0.1] Found 1 match(es) in /sf/log/app.log:\n"
            "12: timeout while connecting"
        ),
        observed_at=observed_at,
    )

    summary = build_log_timeline(events)

    assert "Timeline" not in summary
    assert "No Timestamp Evidence" in summary


def test_build_log_timeline_keeps_partial_parseable_inputs_split_by_section() -> None:
    observed_at = datetime(2026, 3, 18, 10, 30, 0)
    events = extract_log_events(
        target_id="node-a",
        tool_name="read_log_tail",
        content=(
            "[target=root@10.0.0.1] tail 2 lines from /sf/log/app.log:\n"
            "2026-03-18 10:21:03 timeout while connecting\n"
            "retry still failing"
        ),
        observed_at=observed_at,
    )

    summary = build_log_timeline(events)

    assert "Timeline" in summary
    assert "10:21:03 node-a" in summary
    assert "No Timestamp Evidence" in summary
    assert "retry still failing" in summary


def test_build_log_timeline_uses_stable_order_for_identical_timestamps() -> None:
    observed_at = datetime(2026, 3, 18, 10, 30, 0)
    events = []
    events.extend(
        extract_log_events(
            target_id="node-b",
            tool_name="search_log",
            content=(
                "[target=root@10.0.0.2] Found matches in /sf/log/app.log:\n"
                "18: 2026-03-18 10:21:03 timeout while connecting"
            ),
            observed_at=observed_at,
        )
    )
    events.extend(
        extract_log_events(
            target_id="node-a",
            tool_name="search_log",
            content=(
                "[target=root@10.0.0.1] Found matches in /sf/log/app.log:\n"
                "12: 2026-03-18 10:21:03 timeout while connecting"
            ),
            observed_at=observed_at,
        )
    )

    summary = build_log_timeline(events)

    assert summary.index("10:21:03 node-a") < summary.index("10:21:03 node-b")


def test_build_timeline_artifact_preserves_normalized_and_raw_timestamp() -> None:
    observed_at = datetime(2026, 3, 18, 10, 30, 0)
    log_events = extract_log_events(
        target_id="node-a",
        tool_name="read_log_tail",
        content=(
            "[target=root@10.0.0.1] tail 1 lines from /sf/log/app.log:\n"
            "2026-03-18 10:21:03 timeout while connecting"
        ),
        observed_at=observed_at,
    )

    artifact = build_timeline_artifact_from_log_events(
        log_events,
        incident="storage timeout incident",
        target="node-a",
        window_start="2026-03-18T10:21:03",
        window_end="2026-03-18T10:28:41",
        coverage_note="Only evidence with explicit timestamps is included in this timeline.",
    )

    assert artifact.incident == "storage timeout incident"
    assert artifact.target == "node-a"
    assert artifact.window_start == "2026-03-18T10:21:03"
    assert artifact.window_end == "2026-03-18T10:28:41"
    assert artifact.coverage_note == "Only evidence with explicit timestamps is included in this timeline."
    assert artifact.events[0].timestamp_normalized == "2026-03-18T10:21:03"
    assert artifact.events[0].timestamp_raw == "2026-03-18 10:21:03"

    markdown = format_timeline_artifact(artifact)

    assert "# Timeline" in markdown
    assert "Incident: storage timeout incident" in markdown
    assert "Target: node-a" in markdown
    assert "Window: 2026-03-18T10:21:03 to 2026-03-18T10:28:41" in markdown
    assert "Timestamp: 2026-03-18T10:21:03" in markdown
    assert "Evidence: 2026-03-18 10:21:03 timeout while connecting" in markdown
    assert "## Coverage Note" in markdown


def test_format_timeline_artifact_supports_target_only_and_source_only_event_fields() -> None:
    artifact = TimelineArtifact(
        incident=None,
        target=None,
        window_start=None,
        window_end=None,
        coverage_note=None,
        events=[
            TimelineArtifactEvent(
                timestamp_normalized="2026-03-18T10:21:03",
                timestamp_raw="2026-03-18 10:21:03",
                event="service started",
                evidence="2026-03-18 10:21:03 service started",
                target="node-a",
                source=None,
            ),
            TimelineArtifactEvent(
                timestamp_normalized="2026-03-18T10:21:05",
                timestamp_raw="2026-03-18 10:21:05",
                event="timeout spike",
                evidence="2026-03-18 10:21:05 timeout spike",
                target=None,
                source="search_log",
            ),
        ],
    )

    markdown = format_timeline_artifact(artifact)

    assert "- Timestamp: 2026-03-18T10:21:03" in markdown
    assert "  Target: node-a" in markdown
    assert "  Source: search_log" in markdown
    assert markdown.count("Target:") == 1
    assert markdown.count("Source:") == 1


def test_format_timeline_artifact_renders_coverage_note_layout_after_single_event() -> None:
    artifact = TimelineArtifact(
        incident="storage timeout incident",
        target="node-a",
        window_start="2026-03-18T10:21:03",
        window_end="2026-03-18T10:28:41",
        coverage_note="Only evidence with explicit timestamps is included in this timeline.",
        events=[
            TimelineArtifactEvent(
                timestamp_normalized="2026-03-18T10:21:03",
                timestamp_raw="2026-03-18 10:21:03",
                event="service started",
                evidence="2026-03-18 10:21:03 service started",
                target="node-a",
                source="read_log_tail",
            )
        ],
    )

    markdown = format_timeline_artifact(artifact)

    assert "## Events" in markdown
    assert "## Coverage Note" in markdown
    assert "Only evidence with explicit timestamps is included in this timeline." in markdown
    assert "\n\n## Coverage Note\n" in markdown
