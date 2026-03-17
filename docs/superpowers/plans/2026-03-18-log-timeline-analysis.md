# Log Timeline Analysis Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal cross-target log timeline that extracts parseable event times from log evidence, sorts them across targets, highlights near-simultaneous events, and keeps non-parseable evidence visible without faking order.

**Architecture:** Keep collection unchanged and treat timeline generation as a post-processing step on top of existing log-oriented multi-target results. Add a dedicated timeline module for timestamp extraction, event normalization, sorting, and near-event grouping, then append its summary to the existing multi-target troubleshooting summary output.

**Tech Stack:** Python 3.11+, `datetime`, `re`, pytest, pytest-asyncio

---

## Chunk 1: Timestamp Extraction And Event Modeling

### Task 1: Add a dedicated timeline module and event model

**Files:**
- Create: `nanobot/agent/timeline.py`
- Test: `tests/test_log_timeline.py`

- [ ] **Step 1: Write the failing tests**

Add tests that define the minimal event model and timestamp parsing behavior.

Cover:
- parse a standard log prefix with full date and time
- return `unknown` when no parseable timestamp exists
- preserve `target_id`, `tool_name`, `raw_line`, and `observed_at`

Example skeleton:

```python
def test_extract_log_events_parses_timestamp() -> None:
    events = extract_log_events(...)
    assert events[0].time_status == "parsed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_log_timeline.py -k "parse or unknown" -v`
Expected: FAIL because `nanobot.agent.timeline` does not exist

- [ ] **Step 3: Implement the minimal event model**

Create:
- a lightweight event dataclass or typed structure
- timestamp extraction helper(s)
- `extract_log_events(...)`

Event fields must include:
- `target_id`
- `tool_name`
- `event_time`
- `observed_at`
- `raw_line`
- `normalized_message`
- `time_status`

Keep the parser conservative. If a line cannot be parsed confidently, mark it `unknown`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_log_timeline.py -k "parse or unknown" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/timeline.py tests/test_log_timeline.py
git commit -m "feat: add log timeline event extraction"
```

## Chunk 2: Sorting And Near-Event Grouping

### Task 2: Add timeline ordering for parsed events

**Files:**
- Modify: `nanobot/agent/timeline.py`
- Test: `tests/test_log_timeline.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove:
- parsed events are sorted by `event_time`
- unknown-time events do not enter the main timeline
- target identity remains visible after sorting

Example skeleton:

```python
def test_build_timeline_orders_events_across_targets() -> None:
    summary = build_log_timeline(...)
    assert "10:21:03 node-a" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_log_timeline.py -k "orders_events" -v`
Expected: FAIL because sorted timeline rendering is missing

- [ ] **Step 3: Implement minimal sorter and renderer**

Add logic that:
- filters `time_status="parsed"` into the main timeline
- sorts by `event_time`
- renders a `Timeline` section
- places unknown-time items outside the ordered timeline

Do not infer missing dates or timezones in this task.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_log_timeline.py -k "orders_events" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/timeline.py tests/test_log_timeline.py
git commit -m "feat: add ordered cross-target log timeline"
```

### Task 3: Add near-simultaneous event grouping

**Files:**
- Modify: `nanobot/agent/timeline.py`
- Test: `tests/test_log_timeline.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- two similar events within the threshold appear in `Concurrent / Near Events`
- events outside the threshold do not group together

Example skeleton:

```python
def test_build_timeline_groups_near_events() -> None:
    summary = build_log_timeline(...)
    assert "Concurrent / Near Events" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_log_timeline.py -k "near_events" -v`
Expected: FAIL because near-event grouping is missing

- [ ] **Step 3: Implement lightweight grouping**

Add:
- a small threshold constant, e.g. 5 seconds
- message similarity based on `normalized_message`
- summary rendering for grouped near events

Keep the rule deliberately simple. No fuzzy clustering or advanced scoring in V1.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_log_timeline.py -k "near_events" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/timeline.py tests/test_log_timeline.py
git commit -m "feat: add near-event grouping for log timeline"
```

## Chunk 3: Integration With Multi-Target Troubleshooting Output

### Task 4: Append timeline output to log-based multi-target summaries

**Files:**
- Modify: `nanobot/agent/multi_target.py`
- Test: `tests/test_multi_target_troubleshooting.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove:
- log-oriented multi-target results include a `Timeline` section when parseable timestamps exist
- non-log tool summaries do not force timeline output
- unknown-time log evidence appears under `No Timestamp Evidence`

Example skeleton:

```python
def test_aggregate_multi_target_results_includes_log_timeline() -> None:
    summary = aggregate_multi_target_results(...)
    assert "Timeline" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_multi_target_troubleshooting.py -k "timeline" -v`
Expected: FAIL because aggregation does not include timeline rendering

- [ ] **Step 3: Integrate the timeline module**

Update `aggregate_multi_target_results(...)` so that:
- only log-oriented tools attempt timeline generation
- parsed events render under `Timeline`
- grouped close events render under `Concurrent / Near Events`
- unparseable log lines render under `No Timestamp Evidence`

Keep existing `Common Findings`, `Local Findings`, and `Failed Targets`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_multi_target_troubleshooting.py -k "timeline" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/multi_target.py tests/test_multi_target_troubleshooting.py
git commit -m "feat: append log timeline to multi-target summary"
```

## Chunk 4: Edge Cases And Regression Protection

### Task 5: Protect against false timelines and partial parsing

**Files:**
- Modify: `nanobot/agent/timeline.py`
- Test: `tests/test_log_timeline.py`
- Test: `tests/test_multi_target_troubleshooting.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- all-unknown log evidence does not create a fake ordered timeline
- partially parseable inputs keep only parsed lines in the ordered section
- identical timestamps preserve stable ordering with target identity

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_log_timeline.py tests/test_multi_target_troubleshooting.py -k "unknown or partial or stable" -v`
Expected: FAIL because these guards are not implemented

- [ ] **Step 3: Implement the guards**

Add logic that:
- skips `Timeline` when no parsed events exist
- still renders `No Timestamp Evidence`
- keeps deterministic ordering when timestamps are equal

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_log_timeline.py tests/test_multi_target_troubleshooting.py -k "unknown or partial or stable" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/timeline.py tests/test_log_timeline.py tests/test_multi_target_troubleshooting.py
git commit -m "test: cover log timeline edge cases"
```

## Chunk 5: Final Verification

### Task 6: Run focused and adjacent regressions

**Files:**
- Test: `tests/test_log_timeline.py`
- Test: `tests/test_multi_target_troubleshooting.py`
- Test: `tests/test_agentloop_troubleshooting_flow.py`

- [ ] **Step 1: Run focused timeline tests**

Run:

```bash
python3 -m pytest \
  tests/test_log_timeline.py \
  tests/test_multi_target_troubleshooting.py -v
```

Expected:
- all timeline-specific tests PASS
- multi-target summary output remains stable

- [ ] **Step 2: Run adjacent troubleshooting regressions**

Run:

```bash
python3 -m pytest \
  tests/test_agentloop_troubleshooting_flow.py \
  tests/test_agentloop_investigation.py \
  tests/test_troubleshooting_tools.py -v
```

Expected:
- existing troubleshooting loop behavior still PASS
- no regression in log-oriented tool behavior

- [ ] **Step 3: Review diff for boundary control**

Run:

```bash
git diff --stat
git diff -- nanobot/agent/timeline.py nanobot/agent/multi_target.py tests/test_log_timeline.py tests/test_multi_target_troubleshooting.py
```

Expected:
- timeline logic stays concentrated in the planned files
- no accidental changes to unrelated subsystems

- [ ] **Step 4: Commit final integration**

```bash
git add nanobot/agent/timeline.py nanobot/agent/multi_target.py tests/test_log_timeline.py tests/test_multi_target_troubleshooting.py docs/superpowers/specs/2026-03-18-log-timeline-analysis-design.md docs/superpowers/plans/2026-03-18-log-timeline-analysis.md
git commit -m "feat: add cross-target log timeline analysis"
```
