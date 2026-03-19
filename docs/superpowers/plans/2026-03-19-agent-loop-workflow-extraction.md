# AgentLoop Workflow Extraction Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract workflow-specific logic out of `AgentLoop` into focused modules under `nanobot/agent/workflow/` without weakening troubleshooting capability or changing current user-visible behavior.

**Architecture:** Keep `AgentLoop` as the orchestration entrypoint and move four responsibility clusters into function-oriented modules: workflow control, target-expansion gating, troubleshooting result shaping, and investigation feedback rendering. Preserve the existing session metadata keys, precedence rules, and regression coverage while reducing direct logic density in `nanobot/agent/loop.py`.

**Tech Stack:** Python 3.11+, asyncio, pytest, pytest-asyncio

---

## File Structure

- Create: `nanobot/agent/workflow/__init__.py`
  Responsibility: expose the workflow extraction package and keep imports minimal.
- Create: `nanobot/agent/workflow/control.py`
  Responsibility: bounded troubleshooting control parsing, troubleshooting-context detection, and workflow metadata mutation.
- Create: `nanobot/agent/workflow/targeting.py`
  Responsibility: confirmation-gated multi-target scope handling and related scope helpers.
- Create: `nanobot/agent/workflow/result_policy.py`
  Responsibility: evidence-first runtime context and final troubleshooting result shaping.
- Create: `nanobot/agent/workflow/feedback.py`
  Responsibility: progress action/reason/heartbeat/process-summary rendering.
- Modify: `nanobot/agent/loop.py`
  Responsibility: delegate extracted logic to workflow modules while preserving orchestration order.
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
  Responsibility: preserve workflow, targeting, evidence-first, and precedence regressions through `AgentLoop`.
- Modify: `tests/test_agentloop_investigation.py`
  Responsibility: preserve runtime-context, result-shaping, and feedback regressions.
- Modify: `tests/test_exec_dialog_guard.py`
  Responsibility: preserve the `继续` vs exec confirmation regression after extraction.

## Chunk 1: Extract Workflow Control

### Task 1: Move troubleshooting control logic into `workflow/control.py`

**Files:**
- Create: `nanobot/agent/workflow/__init__.py`
- Create: `nanobot/agent/workflow/control.py`
- Modify: `nanobot/agent/loop.py`
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Modify: `tests/test_exec_dialog_guard.py`

- [ ] **Step 1: Add one extraction-focused failing smoke test**

Add a focused regression in `tests/test_agentloop_troubleshooting_flow.py` that proves `AgentLoop` still routes a standalone troubleshooting control turn through the same visible behavior after the extraction boundary is introduced.

Use a direct-turn case that already exists conceptually, but assert the post-extraction public behavior only:

```python
@pytest.mark.asyncio
async def test_process_direct_pause_control_still_works_after_control_extraction(tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    reply = await loop._process_message(
        InboundMessage(channel="cli", sender_id="user", chat_id="direct", content="暂停")
    )
    assert reply is not None
    assert "已暂停当前排查" in reply.content
```

- [ ] **Step 2: Run the focused tests to verify the current baseline**

Run:

```bash
python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k "pause or resume or evidence_first" -v
```

Expected: PASS on the baseline before extraction.

- [ ] **Step 3: Create `workflow/__init__.py` and `workflow/control.py`**

Implement minimal function-oriented exports in `nanobot/agent/workflow/control.py`:

- phrase-boundary helpers
- troubleshooting-content detection
- result-mode gating helpers
- `handle_workflow_control(session, content) -> str | None`

Do not change session metadata keys.

- [ ] **Step 4: Update `AgentLoop` to delegate control handling**

Replace the inline control parsing path in `nanobot/agent/loop.py` with calls into `nanobot.agent.workflow.control`.

Keep these behaviors unchanged:

- `workflow_skip_control_once` still short-circuits control parsing
- `继续` must not steal exec confirmation follow-ups
- `pause/resume/change_focus/narrow_scope/evidence_first` behavior remains identical

- [ ] **Step 5: Run focused regressions**

Run:

```bash
python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k "pause or resume or evidence_first" -v
python3 -m pytest tests/test_exec_dialog_guard.py::test_exec_guard_still_blocks_after_user_confirms_continue -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add nanobot/agent/workflow/__init__.py nanobot/agent/workflow/control.py nanobot/agent/loop.py tests/test_agentloop_troubleshooting_flow.py tests/test_exec_dialog_guard.py
git commit -m "refactor: extract workflow control from agent loop"
```

## Chunk 2: Extract Target Expansion Gate

### Task 2: Move multi-target gating and scope helpers into `workflow/targeting.py`

**Files:**
- Create: `nanobot/agent/workflow/targeting.py`
- Modify: `nanobot/agent/loop.py`
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Modify: `tests/test_agentloop_investigation.py`

- [ ] **Step 1: Add one extraction-focused failing smoke test**

Add a focused regression that proves `AgentLoop` still lets pending target confirmation take precedence over workflow control after the extraction.

```python
@pytest.mark.asyncio
async def test_pending_target_confirmation_still_beats_resume_after_targeting_extraction(tmp_path: Path) -> None:
    ...
```

Assert that a pending target-resolution turn with `继续` still proceeds through target confirmation behavior rather than normal resume behavior.

- [ ] **Step 2: Run the focused baseline tests**

Run:

```bash
python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k "target_expansion or multi_target or precedence or continue" -v
```

Expected: PASS before extraction.

- [ ] **Step 3: Create `workflow/targeting.py`**

Move these helpers into the new module:

- `workflow_allows_confirmed_multi_target`
- `workflow_forbids_multi_target`
- `handle_target_expansion_gate`
- `build_confirmed_scope_progress`
- `clear_confirmed_target_scope`

Pass only the dependencies needed for intent resolution and scope handling.

- [ ] **Step 4: Update `AgentLoop` to call targeting helpers**

Replace inline targeting helpers in `nanobot/agent/loop.py` with module calls, preserving this call order in `_process_message(...)`:

1. target-expansion gate
2. workflow control
3. paused short-circuit

- [ ] **Step 5: Run focused regressions**

Run:

```bash
python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k "target_expansion or multi_target or precedence or continue" -v
python3 -m pytest tests/test_agentloop_investigation.py -k "多节点 or 只查日志" -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add nanobot/agent/workflow/targeting.py nanobot/agent/loop.py tests/test_agentloop_troubleshooting_flow.py tests/test_agentloop_investigation.py
git commit -m "refactor: extract workflow targeting gate from agent loop"
```

## Chunk 3: Extract Evidence-First Result Policy

### Task 3: Move runtime-context and result-shaping logic into `workflow/result_policy.py`

**Files:**
- Create: `nanobot/agent/workflow/result_policy.py`
- Modify: `nanobot/agent/loop.py`
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Modify: `tests/test_agentloop_investigation.py`

- [ ] **Step 1: Add one extraction-focused failing smoke test**

Add a focused regression that proves evidence-first shaping still works through `AgentLoop` after the result-policy extraction boundary is introduced.

```python
def test_evidence_first_result_still_downgrades_strong_conclusion_after_result_policy_extraction():
    ...
```

Keep the assertion user-visible: the final content should contain `当前倾向` and omit undowngraded strong-conclusion wording.

- [ ] **Step 2: Run the focused baseline tests**

Run:

```bash
python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -k "evidence_first or 当前倾向 or inspection or report or case" -v
```

Expected: PASS before extraction.

- [ ] **Step 3: Create `workflow/result_policy.py`**

Move these concerns into the module:

- workflow runtime context construction
- troubleshooting result candidate detection
- structured artifact body detection
- strong-conclusion downgrade helpers
- evidence summarization and evidence-signal counting
- uncertainty / next-step completion
- `shape_evidence_first_result(...)`

- [ ] **Step 4: Update `AgentLoop` to delegate runtime-context and final shaping**

Replace the inline calls in `nanobot/agent/loop.py` so:

- runtime context is built via `result_policy.build_workflow_runtime_context(...)`
- final content is shaped via `result_policy.shape_evidence_first_result(...)`

Do not change the existing call order around `_run_agent_loop(...)`.

- [ ] **Step 5: Run focused regressions**

Run:

```bash
python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -k "evidence_first or 当前倾向 or inspection or report or case" -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add nanobot/agent/workflow/result_policy.py nanobot/agent/loop.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "refactor: extract evidence-first result policy from agent loop"
```

## Chunk 4: Extract Feedback Rendering

### Task 4: Move investigation feedback text rendering into `workflow/feedback.py`

**Files:**
- Create: `nanobot/agent/workflow/feedback.py`
- Modify: `nanobot/agent/loop.py`
- Modify: `tests/test_agentloop_investigation.py`
- Modify: `tests/test_agentloop_troubleshooting_flow.py`

- [ ] **Step 1: Add one extraction-focused failing smoke test**

Add a focused regression that proves the user-visible progress feedback remains unchanged after the feedback renderer is extracted.

At minimum preserve one action string and one heartbeat string through the normal loop path.

- [ ] **Step 2: Run the focused baseline tests**

Run:

```bash
python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -k "heartbeat or process_summary or progress" -v
```

Expected: PASS before extraction.

- [ ] **Step 3: Create `workflow/feedback.py`**

Move these render helpers into the module:

- progress action text
- progress reason text
- multi-target reason text
- heartbeat text
- progress summary text

Keep the module presentation-only.

- [ ] **Step 4: Update `AgentLoop` to call feedback renderers**

Replace internal rendering helper calls with module calls in:

- `_render_progress_reason(...)` call sites
- `_render_progress_action(...)` call sites
- `_render_progress_heartbeat(...)` call sites
- process-summary call sites

- [ ] **Step 5: Run focused regressions**

Run:

```bash
python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -k "heartbeat or process_summary or progress" -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add nanobot/agent/workflow/feedback.py nanobot/agent/loop.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "refactor: extract investigation feedback rendering from agent loop"
```

## Chunk 5: Final Cleanup And Verification

### Task 5: Shrink `AgentLoop` to orchestration-only wiring and verify the full refactor

**Files:**
- Modify: `nanobot/agent/loop.py`
- Modify: `docs/superpowers/plans/2026-03-19-agent-loop-workflow-extraction.md`

- [ ] **Step 1: Remove dead helpers and tighten imports**

Delete helper methods from `nanobot/agent/loop.py` that are no longer used after the extraction, and simplify imports so the file reads as an orchestrator rather than a rule holder.

- [ ] **Step 2: Run the core verification suite**

Run:

```bash
python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py tests/test_exec_dialog_guard.py -v
```

Expected: PASS

- [ ] **Step 3: Run one adjacent regression slice**

Run:

```bash
python3 -m pytest tests/test_commands.py -v
```

Expected: PASS

- [ ] **Step 4: Run a full regression sweep**

Run:

```bash
python3 -m pytest -q
```

Expected: PASS

- [ ] **Step 5: Mark completed plan checkboxes**

Update this plan so completed tasks reflect reality.

- [ ] **Step 6: Commit**

```bash
git add nanobot/agent/loop.py docs/superpowers/plans/2026-03-19-agent-loop-workflow-extraction.md
git commit -m "docs: sync agent loop workflow extraction plan status"
```
