# 排障强反馈 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make troubleshooting progress feel continuously visible and explainable by emitting stage feedback, reasoned investigation cues, long-wait heartbeats, and a short process summary before the final conclusion.

**Architecture:** Keep all changes concentrated around the existing `AgentLoop` progress channel. Introduce a lightweight structured feedback layer near the loop, render bounded progress text programmatically, and reuse the current `on_progress` / bus flow instead of adding a new transport or LLM-generated narration layer.

**Tech Stack:** Python 3.11+, dataclasses, asyncio, pytest, pytest-asyncio

---

## Chunk 1: Structured Feedback Foundations

### Task 1: Map current progress emission boundaries and lock the write scope

**Files:**
- Modify: `docs/superpowers/plans/2026-03-18-troubleshooting-strong-feedback.md`
- Inspect: `nanobot/agent/loop.py`
- Inspect: `tests/test_agentloop_investigation.py`
- Inspect: `tests/test_agentloop_troubleshooting_flow.py`

- [ ] **Step 1: Inspect current progress flow**

Confirm exactly where progress is currently emitted:
- initial phase messages in `_process_message(...)`
- tool-phase messages in `_run_agent_loop(...)`
- confirmed multi-target scope messages

Also identify whether current progress text is already used by CLI and IM flows through the same callback path.

- [ ] **Step 2: Record any discovered helper modules**

If the actual implementation would be clearer with a dedicated helper file (for example `nanobot/agent/feedback.py`), update this plan before coding. Otherwise, keep the logic in `nanobot/agent/loop.py`.

- [ ] **Step 3: No code changes in this task**

This task exists to prevent uncontrolled spread of progress logic.

### Task 2: Add failing tests for structured stage and action feedback

**Files:**
- Modify: `tests/test_agentloop_investigation.py`
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Inspect: `nanobot/agent/loop.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove:
- stage feedback includes the fixed phase set when the loop advances
- action feedback appears when a tool call is about to run
- multi-target execution can emit a distinct action message for fan-out work

Example skeleton:

```python
async def test_run_agent_loop_emits_action_feedback(...) -> None:
    ...
    assert any("正在检查服务状态" in item for item in progress)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest \
  tests/test_agentloop_investigation.py \
  tests/test_agentloop_troubleshooting_flow.py \
  -k "action_feedback or stage_feedback" -v
```

Expected: FAIL because current progress output does not yet expose structured action text.

- [ ] **Step 3: Implement minimal structured feedback helpers**

Update `nanobot/agent/loop.py` so that:
- stage feedback remains stable and fixed
- action feedback is rendered from the current tool call
- multi-target fan-out can produce an explicit multi-target action line

Prefer small internal helpers such as:
- `_render_progress_stage(...)`
- `_render_progress_action(...)`

Do not add `reason`, `heartbeat`, or `summary` in this task yet.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest \
  tests/test_agentloop_investigation.py \
  tests/test_agentloop_troubleshooting_flow.py \
  -k "action_feedback or stage_feedback" -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/loop.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: add structured troubleshooting action feedback"
```

## Chunk 2: Reason Feedback And Process Summary

### Task 3: Add failing tests for `reason` feedback on investigation pivots

**Files:**
- Modify: `tests/test_agentloop_investigation.py`
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Inspect: `nanobot/agent/loop.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove `reason` feedback appears:
- when the first investigation action starts
- when the tool type changes (for example log -> service status)
- when the scope changes from single-target to multi-target

Keep the assertions focused on the existence and shape of the explanation, not exact prose beyond the key relationship.

Example skeleton:

```python
async def test_run_agent_loop_emits_reason_before_first_investigation_action(...) -> None:
    ...
    assert any("所以先检查" in item for item in progress)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest \
  tests/test_agentloop_investigation.py \
  tests/test_agentloop_troubleshooting_flow.py \
  -k "reason_feedback" -v
```

Expected: FAIL because the current loop does not explain why it is checking a specific evidence source.

- [ ] **Step 3: Implement bounded reason generation**

Update `nanobot/agent/loop.py` so that:
- the first investigation action emits a `reason`
- switching evidence sources emits a new `reason`
- multi-target expansion emits a reason tied to scope comparison

Keep the implementation programmatic and bounded. Use tool categories rather than unconstrained generated prose.

Recommended approach:
- classify tools into a few evidence-source buckets (`log`, `service`, `process`, `disk`, `network`, `other`)
- generate short reason templates based on bucket transitions

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest \
  tests/test_agentloop_investigation.py \
  tests/test_agentloop_troubleshooting_flow.py \
  -k "reason_feedback" -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/loop.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: explain why troubleshooting checks are running"
```

### Task 4: Add failing tests for short process summary before the final conclusion

**Files:**
- Modify: `tests/test_agentloop_investigation.py`
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Inspect: `nanobot/agent/loop.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove:
- before the final conclusion, a short process-summary progress message is emitted
- the summary references the major investigation path rather than repeating the entire answer
- multi-target runs can mention comparison or aggregation in the summary

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest \
  tests/test_agentloop_investigation.py \
  tests/test_agentloop_troubleshooting_flow.py \
  -k "process_summary" -v
```

Expected: FAIL because there is no dedicated process-summary event yet.

- [ ] **Step 3: Implement the summary event**

Update `nanobot/agent/loop.py` so that:
- before the final assistant conclusion is emitted, progress includes a short summary message
- the summary uses the tracked investigation path (for example which evidence-source buckets were checked)
- the summary stays within 1-2 short sentences

Use the same bounded investigation-state tracking added for `reason` generation where possible.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest \
  tests/test_agentloop_investigation.py \
  tests/test_agentloop_troubleshooting_flow.py \
  -k "process_summary" -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/loop.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: add troubleshooting process summaries"
```

## Chunk 3: Heartbeats For Long-Running Investigation Steps

### Task 5: Add failing tests for heartbeat feedback

**Files:**
- Modify: `tests/test_agentloop_investigation.py`
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Inspect: `nanobot/agent/loop.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove:
- a long-running tool call can emit a heartbeat after the wait threshold
- repeated heartbeats are throttled rather than spammed
- multi-target fan-out can emit progress heartbeats such as `已完成 2/5`

Prefer mockable time helpers or injectable clocks over real sleep-heavy tests.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest \
  tests/test_agentloop_investigation.py \
  tests/test_agentloop_troubleshooting_flow.py \
  -k "heartbeat" -v
```

Expected: FAIL because current execution waits silently once a tool call is in flight.

- [ ] **Step 3: Implement bounded heartbeat emission**

Update `nanobot/agent/loop.py` so that:
- a tool call can emit a heartbeat after 3 seconds
- repeated heartbeats occur every 5 seconds while still waiting
- fan-out progress can include a simple completed-count heartbeat

Implementation guidance:
- keep the heartbeat logic near tool execution
- prefer an async helper wrapper around tool execution rather than redesigning the tool interface
- keep the first version simple and testable

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest \
  tests/test_agentloop_investigation.py \
  tests/test_agentloop_troubleshooting_flow.py \
  -k "heartbeat" -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/loop.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: add troubleshooting heartbeat feedback"
```

## Chunk 4: Integration Verification And Documentation

### Task 6: Add end-to-end regression coverage for the full strong-feedback path

**Files:**
- Modify: `tests/test_agentloop_investigation.py`
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Modify: `docs/development-status-v1.md`

- [ ] **Step 1: Add focused integration tests**

Cover:
- single-target path with stage + reason + action + summary
- multi-target path with stage + reason + action + heartbeat/aggregation hints + summary

Keep assertions focused on required signals, not incidental exact wording.

- [ ] **Step 2: Run focused verification**

Run:

```bash
python3 -m pytest \
  tests/test_agentloop_investigation.py \
  tests/test_agentloop_troubleshooting_flow.py -v
```

Expected: PASS

- [ ] **Step 3: Update development-status note**

Add a short status update describing that structured troubleshooting feedback now includes:
- stable phases
- reasoned investigation cues
- long-wait heartbeats
- process summary

- [ ] **Step 4: Commit**

```bash
git add tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py docs/development-status-v1.md
git commit -m "test: cover strong troubleshooting feedback flow"
```

### Task 7: Run repository verification and review final diff

**Files:**
- Modify: `nanobot/agent/loop.py`
- Modify: `tests/test_agentloop_investigation.py`
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Modify: `docs/development-status-v1.md`
- Modify: `docs/superpowers/plans/2026-03-18-troubleshooting-strong-feedback.md`

- [ ] **Step 1: Run focused lint**

Run:

```bash
ruff check \
  nanobot/agent/loop.py \
  tests/test_agentloop_investigation.py \
  tests/test_agentloop_troubleshooting_flow.py
```

Expected: PASS

- [ ] **Step 2: Run full test suite**

Run:

```bash
python3 -m pytest
```

Expected: PASS

- [ ] **Step 3: Review final diff**

Run:

```bash
git diff -- \
  nanobot/agent/loop.py \
  tests/test_agentloop_investigation.py \
  tests/test_agentloop_troubleshooting_flow.py \
  docs/development-status-v1.md \
  docs/superpowers/plans/2026-03-18-troubleshooting-strong-feedback.md
```

Verify:
- feedback logic remains bounded near the agent loop
- no new transport layer was introduced
- wording stays short and operator-facing
- summary and heartbeat remain additive rather than noisy

- [ ] **Step 4: Commit**

```bash
git add nanobot/agent/loop.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py docs/development-status-v1.md docs/superpowers/plans/2026-03-18-troubleshooting-strong-feedback.md
git commit -m "feat: strengthen troubleshooting progress feedback"
```
