# Cross-Target Timeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first stable cross-target `timeline_artifact` for log-oriented multi-target troubleshooting so HCIGuard can express shared, near-shared, and local timestamped evidence across targets.

**Architecture:** Reuse the stable multi-target aggregation contract from `nanobot/agent/multi_target.py` and the existing timeline artifact structures in `nanobot/agent/timeline.py`, but insert an explicit cross-target timeline builder between them. The first phase should stay log-only (`search_log`, `read_log_tail`), keep strict timestamp-only admission rules, and produce a valid `timeline_artifact` without absorbing root-cause candidate work.

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio

---

## File Structure

- Modify: `nanobot/agent/timeline.py`
  Responsibility: add the smallest stable cross-target timeline structures and builder helpers needed to produce a `timeline_artifact` from multi-target log evidence.
- Modify: `nanobot/agent/multi_target.py`
  Responsibility: route log-oriented multi-target evidence through the cross-target timeline builder while preserving current aggregation and per-target rendering behavior.
- Modify: `tests/test_log_timeline.py`
  Responsibility: add focused contract and formatter tests for cross-target timeline artifact building.
- Modify: `tests/test_multi_target_troubleshooting.py`
  Responsibility: add multi-target integration tests proving cross-target log evidence can produce a valid timeline artifact without breaking current summaries.
- Modify: `tests/test_result_policy.py`
  Responsibility: add focused classification/regression coverage proving the new cross-target timeline output is still recognized as `timeline_artifact`.
- Modify: `docs/superpowers/plans/2026-03-20-cross-target-timeline.md`
  Responsibility: reflect actual execution status.

## Chunk 1: Lock The Cross-Target Timeline Contract

### Task 1: Add focused failing tests for cross-target timeline artifact building

**Files:**
- Modify: `tests/test_log_timeline.py`

- [x] **Step 1: Write failing tests for shared and local cross-target events**

Add focused tests proving a new cross-target timeline builder can:

- accept log-oriented multi-target evidence from `search_log` / `read_log_tail`
- emit one `timeline_artifact` with shared events when equivalent evidence appears across targets
- emit local events when evidence is only present on one target
- preserve target identity in each event

The event-level contract should lock:

- `timestamp_normalized`
- `timestamp_raw`
- `event`
- `evidence`
- `target`
- `source`
- `scope`

- [x] **Step 2: Write failing tests for strict timestamp-only admission**

Add focused tests proving:

- untimestamped multi-target evidence does not enter the main timeline body
- a coverage note or equivalent exclusion note can still be present
- event ordering remains deterministic for identical or near-identical timestamps

- [x] **Step 3: Run focused cross-target timeline tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_log_timeline.py -k "cross_target or shared_scope or near_shared or local_scope" -v
```

Expected: FAIL because the cross-target timeline builder does not exist yet.

- [x] **Step 4: Commit the red test slice if it is isolated and readable**

```bash
git add tests/test_log_timeline.py
git commit -m "test: add cross-target timeline coverage"
```

If you do not want a red commit on the branch, skip the commit and proceed directly to Task 2.

### Task 2: Implement the cross-target timeline builder and make the tests green

**Files:**
- Modify: `nanobot/agent/timeline.py`
- Modify: `tests/test_log_timeline.py`

- [x] **Step 1: Add the minimal cross-target event structures**

Implement the smallest additions needed to represent cross-target timeline events while staying close to the existing `TimelineArtifact` / `TimelineArtifactEvent` structures.

Keep the first phase narrow:

- log-only evidence
- small stable `scope` vocabulary: `shared`, `near_shared`, `local`
- no extra artifact kinds

- [x] **Step 2: Add the cross-target timeline builder**

Implement the smallest builder that:

- consumes structured multi-target log evidence or extracted log events
- groups events into shared / near-shared / local
- preserves target identity and source evidence
- keeps strict timestamp-only admission rules
- emits a valid `TimelineArtifact`

Do not add root-cause candidate logic in this task.

- [x] **Step 3: Run focused cross-target timeline tests**

Run:

```bash
python3 -m pytest tests/test_log_timeline.py -k "cross_target or shared_scope or near_shared or local_scope" -v
```

Expected: PASS

- [x] **Step 4: Run the full timeline test slice**

Run:

```bash
python3 -m pytest tests/test_log_timeline.py -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add nanobot/agent/timeline.py tests/test_log_timeline.py
git commit -m "feat: add cross-target timeline artifact builder"
```

## Chunk 2: Connect Multi-Target Log Aggregation To Timeline Artifact Output

### Task 3: Add failing integration tests for multi-target cross-target timeline output

**Files:**
- Modify: `tests/test_multi_target_troubleshooting.py`

- [x] **Step 1: Write failing tests for cross-target log timeline integration**

Add focused tests proving that log-oriented multi-target evidence can now produce a cross-target `timeline_artifact` from the aggregation path.

Cover:

- one `search_log` case with shared plus local timestamped evidence
- one `read_log_tail` case with shared or near-shared timestamped evidence
- emitted artifact remains valid Markdown timeline output

- [x] **Step 2: Write failing tests proving state tools do not enter cross-target timeline building**

Add focused tests proving:

- `service_status` and `process_snapshot` continue to stay out of the timeline-artifact path in this phase
- non-log multi-target rendering behavior remains unchanged

- [x] **Step 3: Run focused multi-target timeline integration tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_multi_target_troubleshooting.py -k "cross_target_timeline or timeline_artifact_output" -v
```

Expected: FAIL because the multi-target path does not yet expose the new artifact.

### Task 4: Route multi-target log evidence through the cross-target timeline builder

**Files:**
- Modify: `nanobot/agent/multi_target.py`
- Modify: `tests/test_multi_target_troubleshooting.py`

- [x] **Step 1: Add the minimal integration point in the multi-target log path**

Update the log-oriented multi-target path so it can:

- reuse current per-target raw evidence
- build a cross-target `timeline_artifact` from log-oriented evidence
- keep existing grouped summary behavior intact for this phase

Keep the design narrow:

- no new artifact path for state tools
- no replacement of existing summaries
- no generic report-consumption path yet

- [x] **Step 2: Keep the user-visible output contract conservative**

Choose one stable integration output for this phase and hold it consistent in tests.

Recommended direction:

- keep current grouped summary path as-is
- expose the cross-target timeline artifact through an explicit builder/helper used by later consumers

If you choose to surface the artifact directly in this phase, keep it clearly bounded and do not break current per-target rendering tests.

- [x] **Step 3: Run focused multi-target timeline integration tests**

Run:

```bash
python3 -m pytest tests/test_multi_target_troubleshooting.py -k "cross_target_timeline or timeline_artifact_output" -v
```

Expected: PASS

- [x] **Step 4: Run the full multi-target troubleshooting test file**

Run:

```bash
python3 -m pytest tests/test_multi_target_troubleshooting.py -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add nanobot/agent/multi_target.py tests/test_multi_target_troubleshooting.py
git commit -m "feat: connect multi-target log evidence to timeline artifact"
```

## Chunk 3: Prove Timeline Artifact Classification And Preserve Regressions

### Task 5: Add classification and behavior-preservation regressions

**Files:**
- Modify: `tests/test_result_policy.py`

- [x] **Step 1: Write failing result-policy tests for cross-target timeline artifact recognition**

Add focused tests proving the new cross-target timeline Markdown output:

- still classifies as `timeline_artifact`
- remains rewrite-protected under `shape_evidence_first_result(...)`
- keeps target lists or cross-target scope markers without downgrading classification

- [x] **Step 2: Run focused result-policy tests to verify failure or immediate pass**

Run:

```bash
python3 -m pytest tests/test_result_policy.py -k "timeline_artifact and cross_target" -v
```

Expected: PASS if the existing artifact rules already cover the new output shape, or FAIL if the new shape needs explicit classification support.

If it passes immediately, that is acceptable because the regression coverage is still new.

- [x] **Step 3: Implement the minimal policy adjustment only if needed**

If the focused result-policy tests fail:

- update `result_policy.py` minimally so the new cross-target timeline output still classifies as `timeline_artifact`
- do not broaden classification rules beyond what this output shape needs

If the tests already pass, skip implementation changes and keep the coverage-only slice.

- [x] **Step 4: Run focused result-policy timeline tests**

Run:

```bash
python3 -m pytest tests/test_result_policy.py -k "timeline_artifact or cross_target" -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add tests/test_result_policy.py nanobot/agent/workflow/result_policy.py
git commit -m "test: cover cross-target timeline artifact classification"
```

If `result_policy.py` was not changed, omit it from `git add`.

## Chunk 4: Final Verification And Plan Sync

### Task 6: Run final regressions and sync the plan

**Files:**
- Modify: `docs/superpowers/plans/2026-03-20-cross-target-timeline.md`

- [x] **Step 1: Run focused timeline, multi-target, and policy regressions**

Run:

```bash
python3 -m pytest tests/test_log_timeline.py tests/test_multi_target_troubleshooting.py tests/test_result_policy.py -k "timeline or cross_target or shared_scope or near_shared" -v
```

Expected: PASS

- [x] **Step 2: Run the full timeline/multi-target/policy slices**

Run:

```bash
python3 -m pytest tests/test_log_timeline.py tests/test_multi_target_troubleshooting.py tests/test_result_policy.py -v
```

Expected: PASS

- [x] **Step 3: Optionally run the full suite if no unrelated failures are known**

Run:

```bash
python3 -m pytest -q
```

Expected: PASS, or document any unrelated pre-existing failure clearly.

- [x] **Step 4: Mark completed plan checkboxes**

Update this plan to reflect actual execution status.

- [x] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-03-20-cross-target-timeline.md
git commit -m "docs: sync cross-target timeline plan status"
```
