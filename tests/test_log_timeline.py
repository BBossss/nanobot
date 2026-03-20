from datetime import datetime

import pytest

from nanobot.agent import timeline as timeline_module
from nanobot.agent.timeline import (
    TimelineArtifact,
    TimelineArtifactEvent,
    build_cross_target_timeline_artifact,
    build_log_timeline,
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


def test_build_cross_target_timeline_artifact_emits_shared_and_local_scoped_events() -> None:
    observed_at = datetime(2026, 3, 18, 10, 30, 0)
    events = []
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
            target_id="node-c",
            tool_name="search_log",
            content=(
                "[target=root@10.0.0.3] Found matches in /sf/log/app.log:\n"
                "21: 2026-03-18 10:22:11 permission denied writing to storage backend"
            ),
            observed_at=observed_at,
        )
    )

    artifact = timeline_module.build_cross_target_timeline_artifact(
        events,
        incident="storage timeout incident",
        target_scope="node-a,node-b,node-c",
    )

    assert artifact.incident == "storage timeout incident"
    assert artifact.target == "node-a,node-b,node-c"
    assert artifact.window_start == "2026-03-18T10:21:03"
    assert artifact.window_end == "2026-03-18T10:22:11"
    assert artifact.coverage_note == "Only evidence with explicit timestamps is included in this timeline."
    assert len(artifact.events) == 2

    shared = artifact.events[0]
    assert shared.timestamp_normalized == "2026-03-18T10:21:03"
    assert shared.timestamp_raw == "2026-03-18 10:21:03"
    assert "node-a" in shared.event and "node-b" in shared.event
    assert "timeout while connecting to storage backend" in shared.evidence
    assert shared.target == "node-a,node-b"
    assert shared.source == "search_log,read_log_tail"
    assert shared.scope == "near_shared"

    local = artifact.events[1]
    assert local.timestamp_normalized == "2026-03-18T10:22:11"
    assert local.timestamp_raw == "2026-03-18 10:22:11"
    assert "node-c" in local.event
    assert "permission denied writing to storage backend" in local.evidence
    assert local.target == "node-c"
    assert local.source == "search_log"
    assert local.scope == "local"


def test_build_cross_target_timeline_artifact_excludes_untimestamped_events_from_body() -> None:
    observed_at = datetime(2026, 3, 18, 10, 30, 0)
    events = extract_log_events(
        target_id="node-a",
        tool_name="search_log",
        content=(
            "[target=root@10.0.0.1] Found 2 match(es) in /sf/log/app.log:\n"
            "12: timeout while connecting to storage backend\n"
            "18: retry still failing"
        ),
        observed_at=observed_at,
    )

    artifact = timeline_module.build_cross_target_timeline_artifact(
        events,
        incident="storage timeout incident",
        target_scope="node-a",
    )

    assert artifact.events == []
    assert artifact.coverage_note == "Only evidence with explicit timestamps is included in this timeline."


def test_build_cross_target_timeline_artifact_uses_stable_order_for_identical_timestamp_groups() -> None:
    observed_at = datetime(2026, 3, 18, 10, 30, 0)
    events = []
    events.extend(
        extract_log_events(
            target_id="node-b",
            tool_name="search_log",
            content=(
                "[target=root@10.0.0.2] Found matches in /sf/log/app.log:\n"
                "18: 2026-03-18 10:21:03 timeout while connecting to storage backend"
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
                "12: 2026-03-18 10:21:03 timeout while connecting to storage backend"
            ),
            observed_at=observed_at,
        )
    )
    events.extend(
        extract_log_events(
            target_id="node-c",
            tool_name="search_log",
            content=(
                "[target=root@10.0.0.3] Found matches in /sf/log/app.log:\n"
                "21: 2026-03-18 10:21:03 timeout while connecting to storage backend"
            ),
            observed_at=observed_at,
        )
    )

    artifact = timeline_module.build_cross_target_timeline_artifact(
        events,
        target_scope="node-a,node-b,node-c",
    )

    assert len(artifact.events) == 1
    assert artifact.events[0].target == "node-a,node-b,node-c"
    assert artifact.events[0].scope == "shared"


def test_build_timeline_artifact_preserves_normalized_and_raw_timestamp() -> None:
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
                event="timeout while connecting",
                evidence="2026-03-18 10:21:03 timeout while connecting",
                target="node-a",
                source="read_log_tail",
            )
        ],
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


def test_format_timeline_artifact_raises_on_empty_events() -> None:
    artifact = TimelineArtifact(
        incident="storage timeout incident",
        target="node-a",
        window_start=None,
        window_end=None,
        coverage_note=None,
        events=[],
    )

    try:
        format_timeline_artifact(artifact)
    except ValueError as exc:
        assert "at least one event" in str(exc)
    else:
        raise AssertionError("expected format_timeline_artifact to reject empty events")


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_message"),
    [
        ("timestamp_normalized", " ", "timestamp_normalized"),
        ("timestamp_raw", "", "timestamp_raw"),
        ("event", "", "event"),
        ("evidence", " ", "evidence"),
    ],
)
def test_format_timeline_artifact_rejects_blank_required_event_fields(
    field_name: str,
    field_value: str,
    expected_message: str,
) -> None:
    kwargs = {
        "timestamp_normalized": "2026-03-18T10:21:03",
        "timestamp_raw": "2026-03-18 10:21:03",
        "event": "service started",
        "evidence": "2026-03-18 10:21:03 service started",
        "target": "node-a",
        "source": "read_log_tail",
    }
    kwargs[field_name] = field_value

    artifact = TimelineArtifact(
        incident="storage timeout incident",
        target="node-a",
        window_start=None,
        window_end=None,
        coverage_note=None,
        events=[TimelineArtifactEvent(**kwargs)],
    )

    with pytest.raises(ValueError, match=expected_message):
        format_timeline_artifact(artifact)


def test_format_timeline_artifact_renders_window_start_only() -> None:
    artifact = TimelineArtifact(
        incident="storage timeout incident",
        target="node-a",
        window_start="2026-03-18T10:21:03",
        window_end=None,
        coverage_note=None,
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

    assert "Window start: 2026-03-18T10:21:03" in markdown
    assert "Window:" not in markdown


def test_format_timeline_artifact_renders_window_end_only() -> None:
    artifact = TimelineArtifact(
        incident="storage timeout incident",
        target="node-a",
        window_start=None,
        window_end="2026-03-18T10:28:41",
        coverage_note=None,
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

    assert "Window end: 2026-03-18T10:28:41" in markdown
    assert "Window:" not in markdown


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


def test_build_cross_target_timeline_artifact_emits_shared_scope_and_local_scope_events() -> None:
    artifact = timeline_module.build_cross_target_timeline_artifact(
        tool_name="search_log",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.2] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-c",
                "target_host": "root@10.0.0.3",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.3] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:22:11 permission denied writing to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 22, 30),
            },
        ],
    )

    assert isinstance(artifact, TimelineArtifact)
    assert artifact.target == "node-a,node-b,node-c"
    assert artifact.coverage_note == "Only evidence with explicit timestamps is included in this timeline."
    assert [event.scope for event in artifact.events] == ["shared", "local"]
    assert [event.target for event in artifact.events] == ["node-a,node-b", "node-c"]
    assert [event.source for event in artifact.events] == ["search_log", "search_log"]
    assert all(event.timestamp_normalized for event in artifact.events)
    assert all(event.timestamp_raw for event in artifact.events)
    assert all(event.event for event in artifact.events)
    assert all(event.evidence for event in artifact.events)
    assert "timeout while connecting to storage backend" in artifact.events[0].event
    assert "permission denied writing to storage backend" in artifact.events[1].event


def test_build_cross_target_timeline_artifact_excludes_untimestamped_evidence_from_main_timeline_body() -> None:
    artifact = timeline_module.build_cross_target_timeline_artifact(
        tool_name="read_log_tail",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] tail 2 lines from /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend\n"
                    "worker exited unexpectedly"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.2] tail 1 lines from /sf/log/app.log:\n"
                    "2026-03-20 10:21:04 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
        ],
    )

    assert isinstance(artifact, TimelineArtifact)
    assert "worker exited unexpectedly" not in " ".join(event.event for event in artifact.events)
    assert artifact.coverage_note == "Only evidence with explicit timestamps is included in this timeline."
    assert [event.scope for event in artifact.events] == ["near_shared"]
    assert [event.target for event in artifact.events] == ["node-a,node-b"]


def test_build_cross_target_timeline_artifact_orders_near_shared_timestamps_deterministically() -> None:
    artifact = timeline_module.build_cross_target_timeline_artifact(
        tool_name="search_log",
        results=[
            {
                "target_id": "node-c",
                "target_host": "root@10.0.0.3",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.3] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:21:04 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.2] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
        ],
    )

    assert isinstance(artifact, TimelineArtifact)
    assert [event.target for event in artifact.events] == ["node-a,node-b,node-c"]
    assert [event.scope for event in artifact.events] == ["near_shared"]
    assert [event.timestamp_normalized for event in artifact.events] == ["2026-03-20T10:21:03"]


def test_build_cross_target_timeline_artifact_keeps_same_target_duplicates_local() -> None:
    artifact = timeline_module.build_cross_target_timeline_artifact(
        events=[
            *extract_log_events(
                target_id="node-a",
                tool_name="search_log",
                content=(
                    "[target=root@10.0.0.1] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend"
                ),
                observed_at=datetime(2026, 3, 20, 10, 21, 30),
            ),
            *extract_log_events(
                target_id="node-a",
                tool_name="read_log_tail",
                content=(
                    "[target=root@10.0.0.1] tail 1 lines from /sf/log/app.log:\n"
                    "2026-03-20 10:21:03 timeout while connecting to storage backend"
                ),
                observed_at=datetime(2026, 3, 20, 10, 21, 31),
            ),
        ],
        target_scope="node-a",
    )

    assert isinstance(artifact, TimelineArtifact)
    assert len(artifact.events) == 1
    assert artifact.events[0].scope == "local"
    assert artifact.events[0].target == "node-a"
    assert artifact.events[0].source == "search_log,read_log_tail"


def test_build_cross_target_timeline_artifact_merges_near_shared_chains_across_targets() -> None:
    artifact = timeline_module.build_cross_target_timeline_artifact(
        tool_name="search_log",
        results=[
            {
                "target_id": "node-a",
                "target_host": "root@10.0.0.1",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.1] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:21:00 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 30),
            },
            {
                "target_id": "node-b",
                "target_host": "root@10.0.0.2",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.2] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:21:04 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 31),
            },
            {
                "target_id": "node-c",
                "target_host": "root@10.0.0.3",
                "status": "ok",
                "content": (
                    "[target=root@10.0.0.3] Found matches in /sf/log/app.log:\n"
                    "2026-03-20 10:21:08 timeout while connecting to storage backend"
                ),
                "error": "",
                "observed_at": datetime(2026, 3, 20, 10, 21, 32),
            },
        ],
        target_scope="node-a,node-b,node-c",
    )

    assert isinstance(artifact, TimelineArtifact)
    assert len(artifact.events) == 1
    assert artifact.events[0].scope == "near_shared"
    assert artifact.events[0].target == "node-a,node-b,node-c"
    assert artifact.events[0].timestamp_normalized == "2026-03-20T10:21:00"
