# Result Policy Output Kind Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce an explicit `output kind` classification boundary inside `nanobot/agent/workflow/result_policy.py` while preserving current evidence-first behavior and artifact-protection rules.

**Architecture:** Keep `AgentLoop` unchanged and evolve `result_policy.py` in place. First add a centralized classifier and a single dispatch boundary, then route existing evidence-first shaping through that boundary without changing user-visible behavior. Do not expand timeline/root-cause behavior yet; only create stable landing zones for them.

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio

---

## File Structure

- Modify: `nanobot/agent/workflow/result_policy.py`
  Responsibility: add explicit output-kind classification and route shaping through that classification boundary.
- Create: `tests/test_result_policy.py`
  Responsibility: add focused classification and dispatch tests at the policy boundary.
- Inspect: `tests/test_agentloop_troubleshooting_flow.py`
  Responsibility: preserve end-to-end evidence-first and artifact-bypass behavior through `AgentLoop`.
- Inspect: `tests/test_agentloop_investigation.py`
  Responsibility: preserve runtime-context and troubleshooting follow-up behavior.
- Modify: `docs/superpowers/plans/2026-03-20-result-policy-output-kind.md`
  Responsibility: reflect execution progress accurately.

## Chunk 1: Add Explicit Output Kinds

### Task 1: Introduce a stable output classifier in `result_policy.py`

**Files:**
- Modify: `nanobot/agent/workflow/result_policy.py`
- Create: `tests/test_result_policy.py`

- [ ] **Step 1: Write focused failing classification tests**

Add policy-level tests for these cases:

- troubleshooting natural-language reply classifies as `troubleshooting_reply`
- structured inspection body classifies as `inspection_artifact`
- structured report body classifies as `report_artifact`
- structured case body classifies as `case_artifact`
- unrelated plain reply classifies as `generic_reply`
- reserved timeline-like content classifies as `timeline_artifact`
- reserved root-cause-candidate-like content classifies as `root_cause_candidate`

Keep the tests narrow and deterministic; do not go through `AgentLoop`.

- [ ] **Step 2: Run the classification tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_result_policy.py -k "classif" -v
```

Expected: FAIL because no explicit output-kind classifier exists yet.

- [ ] **Step 3: Implement output-kind classification**

Update `nanobot/agent/workflow/result_policy.py` to add:

- string constants or equivalent stable labels for output kinds
- `classify_output_kind(...)`
- helper functions needed to distinguish troubleshooting replies from structured artifacts and reserved future output kinds

Do not change the visible shaping behavior in this task.

- [ ] **Step 4: Run the classification tests to verify pass**

Run:

```bash
python3 -m pytest tests/test_result_policy.py -k "classif" -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/workflow/result_policy.py tests/test_result_policy.py
git commit -m "refactor: add output kind classification to result policy"
```

## Chunk 2: Dispatch Shaping Through Output Kind

### Task 2: Route evidence-first shaping through the classifier without behavior change

**Files:**
- Modify: `nanobot/agent/workflow/result_policy.py`
- Modify: `tests/test_result_policy.py`
- Inspect: `tests/test_agentloop_troubleshooting_flow.py`

- [ ] **Step 1: Write focused failing dispatch tests**

Add policy-level tests proving:

- `troubleshooting_reply` still gets evidence-first shaping
- `inspection_artifact` remains unchanged
- `report_artifact` remains unchanged
- `case_artifact` remains unchanged
- `generic_reply` remains unchanged

At least one troubleshooting test must assert strong conclusion downgrade still yields `当前倾向`.

- [ ] **Step 2: Run the policy dispatch tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_result_policy.py -k "dispatch or shaping" -v
```

Expected: FAIL because shaping is not yet routed through explicit output kinds.

- [ ] **Step 3: Implement classifier-based dispatch**

Update `shape_evidence_first_result(...)` so it:

1. calls `classify_output_kind(...)`
2. dispatches by kind
3. only applies the current evidence-first logic to `troubleshooting_reply`
4. leaves all other kinds unchanged

Keep current evidence-first helper behavior unchanged inside the troubleshooting branch.

- [ ] **Step 4: Run policy dispatch tests**

Run:

```bash
python3 -m pytest tests/test_result_policy.py -k "dispatch or shaping" -v
```

Expected: PASS

- [ ] **Step 5: Run the existing end-to-end evidence-first regressions**

Run:

```bash
python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -k "evidence_first or 当前倾向 or inspection or report or case" -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add nanobot/agent/workflow/result_policy.py tests/test_result_policy.py
git commit -m "refactor: route result shaping through output kinds"
```

## Chunk 3: Final Verification And Plan Sync

### Task 3: Verify the phase-A output-kind refactor and sync documentation

**Files:**
- Modify: `docs/superpowers/plans/2026-03-20-result-policy-output-kind.md`

- [ ] **Step 1: Run the core verification suite**

Run:

```bash
python3 -m pytest tests/test_result_policy.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -v
```

Expected: PASS

- [ ] **Step 2: Run an adjacent regression slice**

Run:

```bash
python3 -m pytest tests/test_exec_dialog_guard.py tests/test_commands.py -v
```

Expected: PASS

- [ ] **Step 3: Optionally run the full suite if no unrelated failures are already known**

Run:

```bash
python3 -m pytest -q
```

Expected: PASS, or document any unrelated pre-existing failure clearly.

- [ ] **Step 4: Mark completed plan checkboxes**

Update this plan to reflect actual execution.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-03-20-result-policy-output-kind.md
git commit -m "docs: sync result policy output kind plan status"
```
