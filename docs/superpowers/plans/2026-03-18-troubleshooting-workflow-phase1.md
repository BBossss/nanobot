# Troubleshooting Workflow Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add phase 1 interactive troubleshooting controls so users can pause, resume, change investigation focus, and narrow scope without weakening troubleshooting capability.

**Architecture:** Build this as a thin control layer on top of existing session metadata and `AgentLoop` handling rather than introducing a new workflow engine. Normalize both natural language and fixed short commands into a small set of internal control intents, then let those intents constrain subsequent investigation behavior and progress feedback.

**Tech Stack:** Python 3.11, dataclasses, session metadata, asyncio, pytest, pytest-asyncio

---

## Chunk 1: Control Intent Recognition

### Task 1: Add failing tests for phase 1 control intent parsing

**Files:**
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Inspect: `nanobot/agent/loop.py`
- Inspect: `docs/superpowers/specs/2026-03-18-troubleshooting-workflow-phase1-design.md`

- [ ] **Step 1: Write failing tests for recognized control intents**

Add tests that prove both natural language and fixed short commands can be interpreted as the same internal control classes:

- `暂停` -> `pause`
- `继续` -> `resume`
- `只查日志` / `先只看日志` -> `change_focus`
- `不要多节点` / `先别扩到多节点` -> `narrow_scope`

Keep these tests focused on routing/recognition, not full downstream execution yet.

- [ ] **Step 2: Run the targeted tests to confirm failure**

Run:

```bash
python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k "pause or resume or focus or scope" -v
```

Expected: FAIL because no workflow control parser exists yet.

- [ ] **Step 3: Implement minimal control intent parsing**

Update `nanobot/agent/loop.py` to add a small parser/helper that recognizes the initial phase 1 control phrases and maps them to:

- `pause`
- `resume`
- `change_focus`
- `narrow_scope`

Do not add a generic NLP layer. Start with bounded phrase/token recognition only.

- [ ] **Step 4: Run the targeted tests to verify pass**

Run:

```bash
python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k "pause or resume or focus or scope" -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/loop.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: recognize troubleshooting workflow control intents"
```

## Chunk 2: Session State And Control Application

### Task 2: Add failing tests for control state persistence and application

**Files:**
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Inspect: `nanobot/session/manager.py`
- Modify: `nanobot/agent/loop.py`

- [ ] **Step 1: Write failing tests for session control state**

Add tests that prove:

- `pause` stores paused state in session metadata
- `resume` clears paused state
- `change_focus` stores a bounded focus hint
- `narrow_scope` can forbid multi-target expansion in later turns

Prefer `process_direct(...)` tests so the behavior is proven through the real loop entrypoint.

- [ ] **Step 2: Run the tests to confirm failure**

Run:

```bash
python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k "paused state or focus hint or forbid multi-target" -v
```

Expected: FAIL because workflow control metadata is not yet persisted or applied.

- [ ] **Step 3: Implement minimal control state handling**

Update `nanobot/agent/loop.py` so that recognized control intents update session metadata with small bounded state such as:

- `workflow_paused`
- `workflow_focus_hint`
- `workflow_scope_constraints`
- `workflow_last_control_reason`

Do not clear previously collected evidence or rewrite session history.

- [ ] **Step 4: Run the tests to verify pass**

Run:

```bash
python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k "paused state or focus hint or forbid multi-target" -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/loop.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: persist troubleshooting workflow control state"
```

## Chunk 3: Investigation Loop Integration

### Task 3: Add failing tests for pause/resume and scope-constrained investigation

**Files:**
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Modify: `tests/test_agentloop_investigation.py`
- Modify: `nanobot/agent/loop.py`

- [ ] **Step 1: Write failing integration tests**

Add tests that prove:

- after `pause`, the loop does not continue issuing new investigation tool calls
- after `resume`, investigation can continue from existing session context
- after `不要多节点`, later turns do not enter the multi-target confirmation/expansion path
- after `只查日志`, later investigation prioritizes log-oriented checks instead of silently ignoring the hint

Keep assertions bounded and observable. Avoid over-specifying exact prose unless the wording is itself the requirement.

- [ ] **Step 2: Run the integration tests to confirm failure**

Run:

```bash
python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -k "pause or resume or 不要多节点 or 只查日志" -v
```

Expected: FAIL because the current loop does not yet honor phase 1 controls.

- [ ] **Step 3: Implement minimal loop integration**

Update `nanobot/agent/loop.py` so that:

- paused sessions short-circuit with a pause confirmation rather than continuing to investigate
- resume removes the pause gate and returns to normal handling
- scope constraints can block multi-target expansion proposals and confirmed expansion reuse
- focus hints are injected in a bounded way into investigation planning without replacing the agent's judgment

Reuse existing session metadata and target-expansion gates where possible.

- [ ] **Step 4: Run the integration tests to verify pass**

Run:

```bash
python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -k "pause or resume or 不要多节点 or 只查日志" -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/loop.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: apply workflow controls to troubleshooting investigation"
```

## Chunk 4: User-Facing Feedback And Regression Coverage

### Task 4: Add confirmation feedback and protect existing troubleshooting behavior

**Files:**
- Modify: `nanobot/agent/loop.py`
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Modify: `tests/test_agentloop_investigation.py`

- [ ] **Step 1: Write failing tests for control acknowledgements**

Add tests that prove control actions produce concise confirmation feedback, for example:

- `已暂停当前排查；如需继续，请回复“继续”。`
- `后续先按日志方向继续调查。`
- `后续保持单节点模式，不扩到多节点。`

Also keep at least one regression assertion showing that normal troubleshooting still works when no control intent is present.

- [ ] **Step 2: Run the tests to confirm failure**

Run:

```bash
python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -k "control acknowledgement or normal troubleshooting" -v
```

Expected: FAIL because the new acknowledgement copy and flow do not exist yet.

- [ ] **Step 3: Implement bounded acknowledgement rendering**

Update `nanobot/agent/loop.py` so that control actions return short, operationally clear acknowledgements and explain the effective constraint without long freeform narration.

Do not mix these confirmations into generic progress text; keep them explicit and bounded.

- [ ] **Step 4: Run focused tests and a broader regression slice**

Run:

```bash
python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/loop.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: add bounded troubleshooting workflow control feedback"
```

## Chunk 5: Final Verification

### Task 5: Verify the completed phase 1 slice

**Files:**
- Inspect: `nanobot/agent/loop.py`
- Inspect: `tests/test_agentloop_investigation.py`
- Inspect: `tests/test_agentloop_troubleshooting_flow.py`

- [ ] **Step 1: Run the full focused test slice**

Run:

```bash
python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -v
```

Expected: PASS

- [ ] **Step 2: Review diff for scope creep**

Run:

```bash
git diff --stat HEAD~4..HEAD
```

Expected: changes remain concentrated in `AgentLoop` and the two troubleshooting test files.

- [ ] **Step 3: Confirm non-goals remain out of scope**

Manually verify that the implementation does not introduce:

- a workflow engine
- complex plan editing
- automatic remediation
- generalized cross-host orchestration

