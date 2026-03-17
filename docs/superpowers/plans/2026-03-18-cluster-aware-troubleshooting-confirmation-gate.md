# Cluster-Aware Troubleshooting With Confirmation Gate Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add cluster-aware troubleshooting to the interactive agent while keeping single-node behavior as the default and requiring explicit user confirmation before any multi-target investigation runs.

**Architecture:** Reuse existing `targeting` and `resolve_targets(...)` foundations, then add a thin resolver + confirmation gate + orchestrator flow around the current single-target troubleshooting tools. Keep tools single-target; centralize multi-target behavior in agent/session orchestration so later timeline and root-cause work can build on one evidence model.

**Tech Stack:** Python 3.11+, asyncio, Pydantic, pytest, pytest-asyncio

---

## Chunk 1: Session State And Intent Resolution

### Task 1: Define multi-target troubleshooting session state

**Files:**
- Modify: `nanobot/session/manager.py`
- Modify: `nanobot/agent/loop.py`
- Test: `tests/test_agentloop_troubleshooting_flow.py`

- [ ] **Step 1: Write the failing test**

Add a session-level test that models:

```python
async def test_cluster_expansion_requires_explicit_confirmation(...):
    ...
```

Expected behavior:
- first user request only records a pending expansion candidate
- no multi-target tool execution happens yet
- after a confirmation message, the pending candidate can be consumed

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k expansion -v`
Expected: FAIL because no expansion session state exists yet

- [ ] **Step 3: Add minimal session fields**

Extend session state with fields such as:

- `pending_target_resolution`
- `resolved_targets`
- `expansion_confirmed`
- `resolution_reason`

Keep defaults empty so existing sessions remain single-target.

- [ ] **Step 4: Wire state load/save into the agent loop**

Ensure the loop can:
- store a pending expansion proposal
- detect a later confirmation message
- clear the proposal after accept/reject

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k expansion -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add nanobot/session/manager.py nanobot/agent/loop.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: add troubleshooting expansion session state"
```

### Task 2: Add lightweight target intent resolver

**Files:**
- Create: `nanobot/targets/intent_resolver.py`
- Modify: `nanobot/targets/__init__.py`
- Test: `tests/test_target_intent_resolver.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- explicit group-name match
- label/domain keyword match
- no stable match returns no expansion
- over-limit candidate sets are truncated or flagged

Example skeleton:

```python
def test_resolve_intent_from_group_name(...):
    result = resolve_target_intent(...)
    assert result.should_expand is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_target_intent_resolver.py -v`
Expected: FAIL because resolver does not exist

- [ ] **Step 3: Implement the resolver**

Implement a small pure function that:
- accepts user text + targeting config
- matches configured group names directly
- matches labels via simple keyword rules
- returns a structured result with:
  - `group_names`
  - `label_all`
  - `label_any`
  - `reason`
  - `should_expand`
  - `candidate_count`

Do not call tools or mutate session state here.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_target_intent_resolver.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/targets/intent_resolver.py nanobot/targets/__init__.py tests/test_target_intent_resolver.py
git commit -m "feat: add troubleshooting target intent resolver"
```

## Chunk 2: Confirmation Gate In The Interactive Agent

### Task 3: Add expansion confirmation gate behavior

**Files:**
- Modify: `nanobot/agent/loop.py`
- Modify: `nanobot/agent/context.py`
- Test: `tests/test_agentloop_troubleshooting_flow.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- suggestion path: agent replies with candidate nodes and asks for confirmation
- reject path: agent stays single-target
- accept path: agent flips session to multi-target mode for the pending target set

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k confirmation -v`
Expected: FAIL because the loop has no confirmation gate

- [ ] **Step 3: Implement the confirmation gate**

In the loop:
- run intent resolution before normal troubleshooting fan-out
- if `should_expand` and user did not explicitly request multiple targets, do not execute multi-target work yet
- send a confirmation response that includes:
  - reason
  - target list
  - notice that current behavior remains single-target until confirmed

Recognize a narrow set of confirmations, for example:
- `确认`
- `继续`
- `可以查`
- `yes`

Recognize a narrow set of rejections, for example:
- `不用`
- `先单节点`
- `no`

Keep the matcher intentionally simple in V1.

- [ ] **Step 4: Update agent guidance/context**

Adjust agent-facing instructions so the model knows:
- single-target remains default
- it must not silently expand scope
- it should explain why expansion is being suggested

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k "confirmation or expansion" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add nanobot/agent/loop.py nanobot/agent/context.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: require confirmation before multi-target troubleshooting"
```

## Chunk 3: Multi-Target Orchestration And Evidence Shaping

### Task 4: Add orchestrator for selected troubleshooting tools

**Files:**
- Create: `nanobot/agent/multi_target.py`
- Modify: `nanobot/agent/loop.py`
- Test: `tests/test_multi_target_troubleshooting.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove:
- only selected tools are fanned out
- each result is tagged with `target_id`
- one target failure does not abort others

Example skeleton:

```python
@pytest.mark.asyncio
async def test_multi_target_orchestrator_fans_out_selected_tool(...):
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_multi_target_troubleshooting.py -v`
Expected: FAIL because orchestrator does not exist

- [ ] **Step 3: Implement minimal orchestrator**

Implement a helper that:
- accepts resolved targets and a single tool invocation
- supports only:
  - `service_status`
  - `process_snapshot`
  - `search_log`
  - `read_log_tail`
  - `find_logs`
- executes the same call once per target
- wraps outputs into structured evidence records with:
  - `target_id`
  - `target_host`
  - `tool_name`
  - `status`
  - `content`
  - `error`

For unsupported tools, fall back to existing single-target behavior.

- [ ] **Step 4: Integrate orchestrator into the loop**

When session state shows `expansion_confirmed`:
- route supported troubleshooting tool calls through the orchestrator
- continue using the tool registry for actual single-target execution

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_multi_target_troubleshooting.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add nanobot/agent/multi_target.py nanobot/agent/loop.py tests/test_multi_target_troubleshooting.py
git commit -m "feat: add multi-target troubleshooting orchestrator"
```

### Task 5: Add common/local/failure evidence aggregation

**Files:**
- Modify: `nanobot/agent/multi_target.py`
- Test: `tests/test_multi_target_troubleshooting.py`

- [ ] **Step 1: Write the failing tests**

Add tests for an aggregator that groups evidence into:
- common anomalies
- target-specific anomalies
- target failures

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_multi_target_troubleshooting.py -k aggregate -v`
Expected: FAIL because grouped evidence view is missing

- [ ] **Step 3: Implement minimal aggregation**

Use stable text signatures or exact content keys to derive:
- shared evidence present on multiple targets
- evidence present on only one target
- failed targets with reasons

Do not sort by time and do not infer root cause in this task.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_multi_target_troubleshooting.py -k aggregate -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/multi_target.py tests/test_multi_target_troubleshooting.py
git commit -m "feat: add multi-target evidence aggregation"
```

## Chunk 4: User-Facing Output, Limits, And Regression Coverage

### Task 6: Add explicit progress and conclusion formatting

**Files:**
- Modify: `nanobot/agent/loop.py`
- Modify: `nanobot/cli/commands.py`
- Test: `tests/test_agentloop_troubleshooting_flow.py`

- [ ] **Step 1: Write the failing tests**

Verify user-visible output includes:
- suggested target range before confirmation
- confirmed target range after acceptance
- common anomalies vs local anomalies
- failed targets, if any

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k progress -v`
Expected: FAIL because output does not distinguish these states

- [ ] **Step 3: Implement formatting changes**

Update progress/conclusion rendering so it clearly communicates:
- default single-target mode
- pending expansion proposal
- confirmed multi-target scope
- grouped evidence summary

Keep output concise and compatible with existing CLI progress hooks.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k progress -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/loop.py nanobot/cli/commands.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: clarify troubleshooting expansion progress output"
```

### Task 7: Enforce safety limits and preserve single-target fallback

**Files:**
- Modify: `nanobot/agent/loop.py`
- Modify: `nanobot/targets/intent_resolver.py`
- Test: `tests/test_target_intent_resolver.py`
- Test: `tests/test_multi_target_troubleshooting.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- expansion candidate count cap
- unknown intent stays single-target
- unsupported tool stays single-target even after confirmation

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_target_intent_resolver.py tests/test_multi_target_troubleshooting.py -k "limit or fallback" -v`
Expected: FAIL because these guards are not implemented

- [ ] **Step 3: Implement safety guards**

Add:
- a configurable or constant `max_expansion_targets`
- fallback behavior when no stable target resolution exists
- fallback behavior for unsupported tools

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_target_intent_resolver.py tests/test_multi_target_troubleshooting.py -k "limit or fallback" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/loop.py nanobot/targets/intent_resolver.py tests/test_target_intent_resolver.py tests/test_multi_target_troubleshooting.py
git commit -m "test: cover multi-target troubleshooting limits and fallback"
```

## Chunk 5: Final Verification

### Task 8: Run focused regression suite

**Files:**
- Test: `tests/test_target_intent_resolver.py`
- Test: `tests/test_multi_target_troubleshooting.py`
- Test: `tests/test_agentloop_troubleshooting_flow.py`

- [ ] **Step 1: Run focused tests**

Run:

```bash
python3 -m pytest \
  tests/test_target_intent_resolver.py \
  tests/test_multi_target_troubleshooting.py \
  tests/test_agentloop_troubleshooting_flow.py -v
```

Expected:
- all new cluster-aware troubleshooting tests PASS
- no regression in existing single-target troubleshooting flow

- [ ] **Step 2: Run broader troubleshooting regressions**

Run:

```bash
python3 -m pytest \
  tests/test_troubleshooting_tools.py \
  tests/test_target_resolver.py \
  tests/test_inspection_multi_target.py -v
```

Expected:
- existing tool behavior still PASS
- current inspection multi-target foundations remain intact

- [ ] **Step 3: Review diff for scope control**

Run:

```bash
git diff --stat
git diff -- nanobot/agent/loop.py nanobot/agent/context.py nanobot/session/manager.py nanobot/targets/intent_resolver.py nanobot/agent/multi_target.py
```

Expected:
- changes remain concentrated in the planned boundaries
- no accidental broad refactor

- [ ] **Step 4: Commit final integration**

```bash
git add nanobot/agent/loop.py nanobot/agent/context.py nanobot/session/manager.py nanobot/targets/intent_resolver.py nanobot/agent/multi_target.py tests/test_target_intent_resolver.py tests/test_multi_target_troubleshooting.py tests/test_agentloop_troubleshooting_flow.py docs/superpowers/specs/2026-03-18-cluster-aware-troubleshooting-design.md docs/superpowers/plans/2026-03-18-cluster-aware-troubleshooting-confirmation-gate.md
git commit -m "feat: add confirmation-gated cluster troubleshooting"
```

