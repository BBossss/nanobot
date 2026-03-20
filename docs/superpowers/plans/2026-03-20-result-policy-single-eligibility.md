# Result Policy Single Eligibility Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse evidence-first rewrite eligibility onto the output-kind boundary in `result_policy.py` while keeping current user-visible behavior unchanged.

**Architecture:** Keep the change local to `nanobot/agent/workflow/result_policy.py` and its focused tests. Introduce one explicit `kind -> eligibility` helper, route both the evidence-first shaper and the compatibility wrapper through it, and preserve the current troubleshooting rewrite logic below that gate. Keep `is_troubleshooting_result_candidate(...)` available, but convert it into a compatibility shell with optional context and a conservative content-only fallback.

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio

---

## File Structure

- Modify: `nanobot/agent/workflow/result_policy.py`
  Responsibility: define the single eligibility contract, update the compatibility wrapper signature, and route shaping through the same eligibility path.
- Modify: `tests/test_result_policy.py`
  Responsibility: add focused policy tests for wrapper alignment, optional-context behavior, and unchanged evidence-first dispatch behavior.
- Inspect: `tests/test_agentloop_troubleshooting_flow.py`
  Responsibility: preserve existing evidence-first shaping and artifact bypass behavior through `AgentLoop`.
- Inspect: `tests/test_agentloop_investigation.py`
  Responsibility: preserve current investigation/runtime-context behavior during evidence-first flows.
- Modify: `docs/superpowers/plans/2026-03-20-result-policy-single-eligibility.md`
  Responsibility: reflect actual execution progress.

## Chunk 1: Lock The Compatibility Contract

### Task 1: Add focused failing tests for single eligibility behavior

**Files:**
- Modify: `tests/test_result_policy.py`

- [ ] **Step 1: Write focused failing wrapper-alignment tests**

Add policy-level tests proving `is_troubleshooting_result_candidate(...)` agrees with output-kind eligibility for:

- troubleshooting reply
- inspection artifact
- report artifact
- case artifact
- timeline artifact
- root-cause candidate artifact
- generic reply

Also add focused tests proving the wrapper works correctly in both modes:

- with `user_content` present, it follows the same kind path as `classify_output_kind(...)`
- without `user_content`, it uses the content-only fallback conservatively

The no-context coverage must explicitly pin all practical fallback outcomes:

- troubleshooting summary remains eligible
- inspection artifact remains ineligible
- report artifact remains ineligible
- case artifact remains ineligible
- timeline artifact remains ineligible
- root-cause candidate artifact remains ineligible
- generic reply remains ineligible

- [ ] **Step 2: Run the focused wrapper tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_result_policy.py -k "candidate and eligibility" -v
```

Expected: FAIL because `is_troubleshooting_result_candidate(...)` still owns independent heuristics and does not accept optional context.

- [ ] **Step 3: Commit the red test slice if it is cleanly isolated**

If the new failing tests are isolated and readable, commit them before implementation:

```bash
git add tests/test_result_policy.py
git commit -m "test: add result policy eligibility alignment coverage"
```

If you prefer not to commit a red state on this branch, skip the commit and proceed directly to Task 2.

## Chunk 2: Collapse Eligibility Onto Output Kind

### Task 2: Implement a single eligibility contract in `result_policy.py`

**Files:**
- Modify: `nanobot/agent/workflow/result_policy.py`
- Modify: `tests/test_result_policy.py`

- [ ] **Step 1: Add a single output-kind eligibility helper**

Implement a small helper such as:

```python
def is_output_kind_rewrite_eligible(kind: str) -> bool:
    return kind == OUTPUT_KIND_TROUBLESHOOTING_REPLY
```

Keep it intentionally narrow and explicit.

- [ ] **Step 2: Upgrade the compatibility wrapper signature**

Update:

```python
def is_troubleshooting_result_candidate(
    content: str,
    user_content: str | None = None,
    messages: list[dict[str, Any]] | None = None,
) -> bool:
```

Behavior:

- if `user_content` is provided, call `classify_output_kind(...)` and return `is_output_kind_rewrite_eligible(kind)`
- if `user_content` is absent, use a conservative content-only fallback classifier that returns a kind, then map that kind through the same eligibility helper

The fallback must not return rewrite decisions directly.

- [ ] **Step 3: Extend focused dispatch coverage before changing the shaper**

Add policy-level tests proving:

- `shape_evidence_first_result(...)` still rewrites `troubleshooting_reply`
- `inspection_artifact` stays unchanged
- `report_artifact` stays unchanged
- `case_artifact` stays unchanged
- `timeline_artifact` stays unchanged
- `root_cause_candidate` stays unchanged
- `generic_reply` stays unchanged

Keep at least one troubleshooting shaping assertion that still checks the strong-conclusion downgrade produces `当前倾向`.

- [ ] **Step 4: Update `shape_evidence_first_result(...)` to use only the single eligibility contract**

Refactor it so that it:

1. classifies once
2. returns unchanged when the kind is not rewrite-eligible
3. preserves the existing troubleshooting rewrite logic inside the eligible branch
4. no longer depends on an independent policy gate

The visible output for current troubleshooting replies must remain unchanged.

- [ ] **Step 5: Run focused policy tests**

Run:

```bash
python3 -m pytest tests/test_result_policy.py -k "candidate and eligibility or dispatch or shaping or timeline or root" -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add nanobot/agent/workflow/result_policy.py tests/test_result_policy.py
git commit -m "refactor: collapse result policy eligibility onto output kinds"
```

## Chunk 3: Verify Behavior Preservation And Sync Plan

### Task 3: Run regressions and update plan status

**Files:**
- Modify: `docs/superpowers/plans/2026-03-20-result-policy-single-eligibility.md`

- [x] **Step 1: Run the focused result-policy and troubleshooting regressions**

Run:

```bash
python3 -m pytest tests/test_result_policy.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -k "candidate or eligibility or evidence_first or 当前倾向 or inspection or report or case or timeline or root" -v
```

Expected: PASS

- [x] **Step 2: Run the full result-policy file**

Run:

```bash
python3 -m pytest tests/test_result_policy.py -v
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
git add docs/superpowers/plans/2026-03-20-result-policy-single-eligibility.md
git commit -m "docs: sync single eligibility result policy plan status"
```
