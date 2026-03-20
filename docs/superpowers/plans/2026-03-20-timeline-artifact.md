# Timeline Artifact Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a first stable `timeline_artifact` for incident timelines, with strict timestamped-event structure, conservative classification, and rewrite protection.

**Architecture:** Reuse existing log timeline extraction in `nanobot/agent/timeline.py`, but add a stable artifact formatter layer and tighten `result_policy.py` classification around a valid timeline event body. The first phase should focus on Markdown artifact shape, minimal internal structure, and policy tests; do not redesign the timeline extractor or broaden source parsing rules.

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio

---

## File Structure

- Modify: `nanobot/agent/timeline.py`
  Responsibility: add the smallest formatter/schema helpers needed to render a stable timeline artifact from already-parsed timeline events.
- Modify: `nanobot/agent/workflow/result_policy.py`
  Responsibility: tighten `timeline_artifact` classification so valid event-body structure is required, while preserving rewrite bypass behavior.
- Modify: `tests/test_log_timeline.py`
  Responsibility: add formatter/schema tests for stable artifact shape without rewriting existing extractor behavior.
- Modify: `tests/test_result_policy.py`
  Responsibility: add focused timeline-artifact classification and bypass regressions, including malformed-heading negatives.
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
  Responsibility: add one timeline-specific evidence-first bypass regression through `AgentLoop` and preserve existing artifact bypass behavior.
- Modify: `docs/superpowers/plans/2026-03-20-timeline-artifact.md`
  Responsibility: reflect actual execution status.

## Chunk 1: Lock The Artifact Boundary

### Task 1: Add focused failing policy tests for stable timeline artifact recognition

**Files:**
- Modify: `tests/test_result_policy.py`

- [x] **Step 1: Write focused failing timeline-artifact policy tests**

Add policy-level tests for:

- canonical Markdown timeline artifact with `# Timeline`, `## Events`, and event entries containing `Timestamp`, `Event`, `Evidence` classifies as `timeline_artifact`
- frontmatter-marked timeline artifact with the same valid event body classifies as `timeline_artifact`
- malformed `# Timeline` heading without valid event entries does not classify as `timeline_artifact`
- frontmatter timeline marker with invalid body does not classify as `timeline_artifact`
- troubleshooting reply with timestamp mentions does not classify as `timeline_artifact`
- `Timestamp/Event/Evidence` body without explicit timeline marker does not classify as `timeline_artifact`
- timeline artifact with valid event body remains unchanged under `shape_evidence_first_result(...)`

At least one unchanged-shaping test must assert a valid `Timestamp/Event/Evidence` timeline body is returned byte-for-byte.

- [x] **Step 2: Run the focused timeline policy tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_result_policy.py -k "timeline_artifact or malformed_timeline or timeline_body" -v
```

Expected: FAIL because current timeline classification is marker-based and does not require valid event-body shape.

- [ ] **Step 3: Commit the red test slice if it is cleanly isolated**

If the failing tests are isolated and readable:

```bash
git add tests/test_result_policy.py
git commit -m "test: add stable timeline artifact policy coverage"
```

If you do not want a red commit on this branch, skip the commit and proceed directly to Task 2.

### Task 2: Tighten timeline classification first and make policy tests green

**Files:**
- Modify: `nanobot/agent/workflow/result_policy.py`
- Modify: `tests/test_result_policy.py`

- [x] **Step 1: Implement valid timeline event-body detection**

Update `result_policy.py` so `timeline_artifact` classification requires both:

- timeline intent marker (`# Timeline`, `# Event Timeline`, or explicit frontmatter marker)
- valid event-body shape, including at least one event entry with `Timestamp`, `Event`, and `Evidence`

Keep the detection conservative:

- timestamp mentions alone must not qualify
- malformed timeline headings must not qualify
- frontmatter markers with invalid body must not qualify
- `Timestamp/Event/Evidence` bodies without explicit timeline markers must not qualify
- ordinary troubleshooting replies remain shapeable

- [x] **Step 2: Run focused timeline policy tests**

Run:

```bash
python3 -m pytest tests/test_result_policy.py -k "timeline_artifact or malformed_timeline or timeline_body" -v
```

Expected: PASS

- [x] **Step 3: Run broader result-policy regressions**

Run:

```bash
python3 -m pytest tests/test_result_policy.py -k "timeline or evidence_first or shaping or candidate or eligibility" -v
```

Expected: PASS

- [x] **Step 4: Commit**

```bash
git add nanobot/agent/workflow/result_policy.py tests/test_result_policy.py
git commit -m "refactor: tighten stable timeline artifact classification"
```

## Chunk 2: Add Stable Timeline Artifact Formatting

### Task 3: Add minimal timeline artifact structure and formatter helpers

**Files:**
- Modify: `nanobot/agent/timeline.py`
- Modify: `tests/test_log_timeline.py`

- [x] **Step 1: Write failing formatter/schema tests**

Add focused tests proving the formatter layer can produce a stable timeline artifact representation from parsed timeline inputs.

Cover:

- artifact-level metadata supports optional `incident`, `target`, `window_start`, `window_end`, `coverage_note`
- event entries carry `timestamp_normalized`, `timestamp_raw`, `event`, `evidence`, optional `target`, optional `source`
- Markdown output renders:
  - `# Timeline`
  - optional metadata lines
  - `## Events`
  - event entries with `Timestamp`, `Event`, `Evidence`
  - optional `Target`, `Source`
  - optional `## Coverage Note`
- normalized timestamp is displayed in Markdown while raw timestamp remains preserved in structure

Keep these tests formatter-scoped; do not redesign `extract_log_events(...)`.

- [x] **Step 2: Run formatter/schema tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_log_timeline.py -k "artifact or formatter or normalized" -v
```

Expected: FAIL because the stable artifact formatter/schema does not exist yet.

- [x] **Step 3: Implement minimal formatter/schema support**

Add the smallest set of helpers in `nanobot/agent/timeline.py` needed to:

- represent timeline artifact metadata and events
- format them into the stable Markdown shape defined in the spec

Keep extraction behavior unchanged. If new dataclasses are needed, keep them local and minimal.

- [x] **Step 4: Run formatter/schema tests to verify pass**

Run:

```bash
python3 -m pytest tests/test_log_timeline.py -k "artifact or formatter or normalized" -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add nanobot/agent/timeline.py tests/test_log_timeline.py
git commit -m "feat: add stable timeline artifact formatter"
```

## Chunk 3: Add AgentLoop Rewrite-Protection Regression

### Task 4: Add one end-to-end timeline artifact bypass regression

**Files:**
- Modify: `tests/test_agentloop_troubleshooting_flow.py`

- [x] **Step 1: Write a failing AgentLoop regression**

Add one focused end-to-end test proving a valid timeline artifact body remains unchanged when `workflow_result_mode = evidence_first`.

Use a realistic body with:

- `# Timeline`
- `## Events`
- at least one event containing `Timestamp`, `Event`, and `Evidence`

- [x] **Step 2: Run the focused AgentLoop regression to verify current behavior**

Run:

```bash
python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k "timeline artifact" -v
```

Expected: PASS if behavior is already preserved, or FAIL if the integration path is not yet protected.

If it passes immediately, that is acceptable because the test is still new regression coverage.

- [x] **Step 3: Commit**

```bash
git add tests/test_agentloop_troubleshooting_flow.py
git commit -m "test: cover timeline artifact rewrite bypass"
```

## Chunk 4: Final Verification And Plan Sync

### Task 5: Verify behavior preservation and sync documentation

**Files:**
- Modify: `docs/superpowers/plans/2026-03-20-timeline-artifact.md`

- [x] **Step 1: Run focused timeline and troubleshooting regressions**

Run:

```bash
python3 -m pytest tests/test_log_timeline.py tests/test_result_policy.py tests/test_agentloop_troubleshooting_flow.py -k "timeline or evidence_first or shaping or malformed" -v
```

Expected: PASS

- [x] **Step 2: Run the full policy and timeline slices**

Run:

```bash
python3 -m pytest tests/test_log_timeline.py tests/test_result_policy.py -v
```

Expected: PASS

- [ ] **Step 3: Optionally run the full suite if no unrelated failures are known**

Run:

```bash
python3 -m pytest -q
```

Expected: PASS, or document any unrelated pre-existing failure clearly.

- [x] **Step 4: Mark completed plan checkboxes**

Update this plan to reflect actual execution status.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-03-20-timeline-artifact.md
git commit -m "docs: sync timeline artifact plan status"
```
