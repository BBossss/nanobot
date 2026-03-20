# Cross-Target Timeline Summary Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface a short cross-target timeline conclusion inside final multi-target troubleshooting replies while keeping the full timeline artifact internal and reusable.

**Architecture:** Reuse the existing `MultiTargetAggregation` and cross-target `timeline_artifact` builder, but add one narrow summary helper that returns a short Chinese troubleshooting sentence. Pass that summary explicitly through `AgentLoop` into `result_policy.shape_evidence_first_result(...)` so output shaping can inject it without reparsing rendered Markdown or storing raw aggregation objects in session metadata.

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio

---

## File Structure

- Modify: `nanobot/agent/multi_target.py`
  Responsibility: add a bounded `build_cross_target_timeline_summary(...)` helper that reuses the existing artifact builder and returns `None` when no stable summary should be emitted.
- Modify: `nanobot/agent/workflow/result_policy.py`
  Responsibility: accept an optional `timeline_summary` input in evidence-first shaping and inject it conservatively into the visible evidence body.
- Modify: `nanobot/agent/loop.py`
  Responsibility: pass a derived current-turn timeline summary string into final result shaping without storing aggregation state in session metadata.
- Modify: `tests/test_multi_target_troubleshooting.py`
  Responsibility: add red/green unit coverage for aggregation-level summary generation.
- Modify: `tests/test_result_policy.py`
  Responsibility: add red/green coverage for evidence-first insertion behavior and the non-insertion guard paths.
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
  Responsibility: add one focused end-to-end flow proving a multi-target troubleshooting reply includes the inserted timeline summary while remaining a troubleshooting reply.
- Modify: `docs/superpowers/plans/2026-03-21-cross-target-timeline-summary.md`
  Responsibility: reflect actual execution status.

## Chunk 1: Add Aggregation-Level Timeline Summary

### Task 1: Add failing tests for cross-target timeline summary generation

**Files:**
- Modify: `tests/test_multi_target_troubleshooting.py`

- [x] **Step 1: Write a failing shared-plus-local summary test**

Add a focused test proving `MultiTargetAggregation.build_cross_target_timeline_summary(...)` returns a short summary like:

```python
assert summary == (
    "时间线补充：最早在 10:21:03 由 node-a,node-b 出现同类超时；"
    "10:22:11 起 node-c 出现本地 permission denied。"
)
```

Use a `search_log` aggregation with:

- one shared or shared-set earliest cluster across `node-a,node-b`
- one later local-only event on `node-c`

- [x] **Step 2: Write a failing near-shared summary test**

Add a focused test proving a near-shared first cluster renders a stable summary like:

```python
assert summary == (
    "时间线补充：最早在 10:21:03 由 node-a 出现超时，"
    "node-b 随后近同时出现同类异常。"
)
```

Use `read_log_tail` or `search_log` input with one near-shared cluster and no later local event.

- [x] **Step 3: Write failing guard tests for no-summary paths**

Add focused tests proving the helper returns `None` when:

- no timestamped log events exist
- the tool is `service_status`
- the artifact effectively has only one target in its admitted timeline body

- [x] **Step 4: Run focused tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_multi_target_troubleshooting.py -k "timeline_summary" -v
```

Expected: FAIL because `build_cross_target_timeline_summary(...)` does not exist yet.

- [x] **Step 5: Commit the red test slice if isolated**

```bash
git add tests/test_multi_target_troubleshooting.py
git commit -m "test: add cross-target timeline summary coverage"
```

If you do not want a red commit, skip the commit and continue directly to Task 2.

### Task 2: Implement the aggregation-level timeline summary helper

**Files:**
- Modify: `nanobot/agent/multi_target.py`
- Modify: `tests/test_multi_target_troubleshooting.py`

- [x] **Step 1: Add the minimal summary helper**

Implement `build_cross_target_timeline_summary(...)` on `MultiTargetAggregation`.

The helper must:

- return `None` for non-log tools
- reuse `build_cross_target_timeline_artifact(...)`
- return `None` if no artifact exists or `artifact.events` is empty
- return `None` if the admitted timeline body is effectively single-target

- [x] **Step 2: Render stable summary strings from the artifact**

Implement the smallest rendering logic that:

- inspects the earliest artifact event
- names the earliest target or target set
- distinguishes `shared` vs `near_shared`
- appends one later local-only event when present
- keeps wording deterministic and short

Do not add generic NL summarization or LLM-based rewriting in this task.

- [x] **Step 3: Run focused summary tests**

Run:

```bash
python3 -m pytest tests/test_multi_target_troubleshooting.py -k "timeline_summary" -v
```

Expected: PASS

- [x] **Step 4: Run the full multi-target troubleshooting file**

Run:

```bash
python3 -m pytest tests/test_multi_target_troubleshooting.py -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add nanobot/agent/multi_target.py tests/test_multi_target_troubleshooting.py
git commit -m "feat: add cross-target timeline summary helper"
```

## Chunk 2: Inject Timeline Summary Into Evidence-First Result Shaping

### Task 3: Add failing result-policy tests for timeline summary insertion

**Files:**
- Modify: `tests/test_result_policy.py`

- [x] **Step 1: Write a failing evidence-first insertion test**

Add a focused test proving `shape_evidence_first_result(...)` inserts a provided `timeline_summary` into the evidence body of a troubleshooting reply.

Use input shaped like:

```python
final_content = (
    "已确认事实：日志里连续出现超时。\n"
    "根因已确认就是存储后端连接不稳定。"
)
```

Expected output should include both:

- the existing `已确认事实`
- the inserted `时间线补充：...`

- [x] **Step 2: Write failing non-insertion guard tests**

Add focused tests proving no summary is inserted when:

- `timeline_summary is None`
- final output is already a `timeline_artifact`
- final output already contains the exact marker `时间线补充：`
- output kind is not rewrite-eligible

- [x] **Step 3: Run focused result-policy tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_result_policy.py -k "timeline_summary" -v
```

Expected: FAIL because the shaping path does not yet accept `timeline_summary`.

### Task 4: Implement timeline-summary-aware result shaping

**Files:**
- Modify: `nanobot/agent/workflow/result_policy.py`
- Modify: `tests/test_result_policy.py`

- [x] **Step 1: Extend the shaping API minimally**

Update `shape_evidence_first_result(...)` to accept an optional `timeline_summary: str | None = None`.

Do not alter classification logic or artifact-kind detection in this task.

- [x] **Step 2: Insert the summary conservatively**

Implement the smallest logic that:

- only acts for rewrite-eligible troubleshooting replies
- skips insertion if `timeline_summary` is missing
- skips insertion if `final_content` already contains `时间线补充：`
- inserts the summary into the evidence body before uncertainty/next-step completion

Keep the insertion deterministic and line-oriented.

- [x] **Step 3: Run focused result-policy tests**

Run:

```bash
python3 -m pytest tests/test_result_policy.py -k "timeline_summary" -v
```

Expected: PASS

- [x] **Step 4: Run the full result-policy file**

Run:

```bash
python3 -m pytest tests/test_result_policy.py -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add nanobot/agent/workflow/result_policy.py tests/test_result_policy.py
git commit -m "feat: inject cross-target timeline summary into evidence-first replies"
```

## Chunk 3: Pass Current-Turn Timeline Summary Through AgentLoop

### Task 5: Add failing troubleshooting-flow coverage for inserted timeline summary

**Files:**
- Modify: `tests/test_agentloop_troubleshooting_flow.py`

- [x] **Step 1: Write a failing multi-target evidence-first flow test**

Add one focused test proving a multi-target troubleshooting turn:

- executes a supported log-oriented tool across multiple targets
- produces a final troubleshooting reply containing `时间线补充：`
- still classifies or behaves like a troubleshooting reply rather than a timeline artifact

Use a bounded fake provider/tool setup consistent with existing flow tests.

- [x] **Step 2: Run focused troubleshooting-flow test to verify failure**

Run:

```bash
python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k "timeline_summary" -v
```

Expected: FAIL because `AgentLoop` does not yet pass the summary into result shaping.

### Task 6: Wire AgentLoop to pass current-turn timeline summary

**Files:**
- Modify: `nanobot/agent/loop.py`
- Modify: `tests/test_agentloop_troubleshooting_flow.py`

- [x] **Step 1: Identify the current-turn multi-target aggregation boundary**

Before coding, verify where the current-turn multi-target tool output is available in `AgentLoop` and keep the implementation bounded to current-turn data only.

- [x] **Step 2: Pass a derived timeline summary string into result shaping**

Implement the smallest wiring so that:

- the current turn can derive `timeline_summary` from multi-target log aggregation output
- only the summary string is passed forward
- no aggregation object is stored in session metadata
- no chronology logic is duplicated in `AgentLoop`

- [x] **Step 3: Run focused troubleshooting-flow tests**

Run:

```bash
python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k "timeline_summary" -v
```

Expected: PASS

- [x] **Step 4: Run the full troubleshooting-flow slice if touched tests remain local**

Run:

```bash
python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add nanobot/agent/loop.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: pass cross-target timeline summaries into troubleshooting replies"
```

## Chunk 4: Final Verification And Plan Sync

### Task 7: Run final regressions and sync the plan

**Files:**
- Modify: `docs/superpowers/plans/2026-03-21-cross-target-timeline-summary.md`

- [x] **Step 1: Run focused regressions**

Run:

```bash
python3 -m pytest tests/test_multi_target_troubleshooting.py tests/test_result_policy.py tests/test_agentloop_troubleshooting_flow.py -k "timeline_summary or cross_target" -v
```

Expected: PASS

- [x] **Step 2: Run the full touched slices**

Run:

```bash
python3 -m pytest tests/test_multi_target_troubleshooting.py tests/test_result_policy.py tests/test_agentloop_troubleshooting_flow.py -v
```

Expected: PASS

- [x] **Step 3: Optionally run the full suite if no unrelated failures are known**

Run:

```bash
python3 -m pytest -q
```

Expected: PASS, or document any unrelated pre-existing failure clearly.

- [x] **Step 4: Mark completed plan checkboxes**

Update this plan to reflect what actually ran and what was committed.

- [x] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-03-21-cross-target-timeline-summary.md
git commit -m "docs: sync cross-target timeline summary plan status"
```
