# Troubleshooting Workflow Phase 2 Evidence-First Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a phase 2 troubleshooting result-mode that keeps troubleshooting investigation strong while forcing evidence-first conclusion shaping until the user explicitly allows direct judgment again.

**Architecture:** Extend the existing phase 1 workflow-control pattern in `AgentLoop` with a new troubleshooting-only `workflow_result_mode` session state and a bounded parser for enable/disable phrases. Apply the mode at the natural-language result layer after investigation runs, so tool choice and investigation progress stay intact while final troubleshooting summaries are reshaped into evidence, uncertainty, next step, and optional low-confidence tendency output.

**Tech Stack:** Python 3.11, asyncio, session metadata, pytest, pytest-asyncio

---

## File Structure

- Modify: `nanobot/agent/loop.py`
  Responsibility: recognize the new result-mode control, persist session state, enforce precedence with existing gates, inject bounded runtime context, and post-process troubleshooting conclusions into evidence-first output.
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
  Responsibility: direct-turn control recognition, state persistence, precedence, and troubleshooting-only scope coverage.
- Modify: `tests/test_agentloop_investigation.py`
  Responsibility: evidence-first integration coverage at the investigation loop boundary, including “do not weaken troubleshooting” regression tests and result-shaping assertions.
- Inspect: `docs/superpowers/specs/2026-03-19-troubleshooting-workflow-phase2-evidence-first-design.md`
  Responsibility: design source of truth for behavior boundaries and precedence.

## Chunk 1: Result-Mode Control Recognition And State

### Task 1: Add failing tests for evidence-first control recognition and persistence

**Files:**
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Inspect: `nanobot/agent/loop.py`
- Inspect: `docs/superpowers/specs/2026-03-19-troubleshooting-workflow-phase2-evidence-first-design.md`

- [x] **Step 1: Write the failing tests for enabling and disabling `evidence_first`**

Add focused `process_direct(...)` tests that prove:

- `先别急着下结论` enables `workflow_result_mode == "evidence_first"`
- `先给证据再说判断` also enables the same mode
- `先别定性` also enables the same mode
- `先证据后判断` also enables the same mode
- `直接说结论` clears `workflow_result_mode`
- `你可以下判断了` clears `workflow_result_mode`
- `直接给判断` also clears the same mode

Assert that `workflow_result_mode_reason` and `workflow_last_control_input` are updated consistently with the existing phase 1 control style, and that disabling the mode clears both `workflow_result_mode` and `workflow_result_mode_reason`.

- [x] **Step 2: Add a failing test that non-control troubleshooting requests do not create result-mode state**

Add a direct-turn regression test showing a normal troubleshooting prompt such as `storage 集群出问题了` leaves `workflow_result_mode`, `workflow_result_mode_reason`, and `workflow_last_control_input` unset.

- [x] **Step 3: Add a failing cross-turn persistence test**

Add a two-turn test that:

- enables `evidence_first`
- sends a normal troubleshooting follow-up turn
- asserts `workflow_result_mode == "evidence_first"` and `workflow_result_mode_reason` are still present before explicit disable

Keep this focused on session persistence, not output shaping.

- [x] **Step 4: Run the focused tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k "evidence_first or 下结论 or 先给证据" -v
```

Expected: FAIL because `AgentLoop` does not yet parse or persist result-mode controls.

- [x] **Step 5: Implement minimal control parsing and state persistence**

Update `nanobot/agent/loop.py` to:

- extend the bounded control parser with result-mode enable/disable phrases
- persist `workflow_result_mode`, `workflow_result_mode_reason`, and `workflow_last_control_input`
- return short cockpit-style acknowledgements for enable and disable actions

Do not reshape any output yet in this task.

- [x] **Step 6: Run the focused tests to verify pass**

Run:

```bash
python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k "evidence_first or 下结论 or 先给证据" -v
```

Expected: PASS

- [x] **Step 7: Commit**

```bash
git add nanobot/agent/loop.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: add evidence-first troubleshooting result mode state"
```

## Chunk 2: Precedence And Troubleshooting-Only Scope

### Task 2: Add failing tests for precedence with existing gates and non-global scope

**Files:**
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Inspect: `nanobot/agent/loop.py`

- [x] **Step 1: Write the failing precedence tests**

Add tests that prove:

- `/new` still resets the session and does not get interpreted as result-mode control
- a pending target expansion confirmation reply such as `继续` is consumed by the pending gate before result-mode logic
- a paused session receiving `继续` resumes troubleshooting before any result-mode logic
- if a turn matches existing investigation controls and result-mode phrasing together, the existing investigation control wins and result-mode does not stack onto the same turn

Use bounded inputs that match the spec precedence table instead of broad NLP cases.

- [x] **Step 2: Write the failing scope-boundary tests**

Add tests that prove:

- ordinary non-troubleshooting chat does not trigger result-mode logic
- evidence-first is recognized only on troubleshooting turns and troubleshooting control turns
- inspection/report/case schema generation paths are not rewritten by merely enabling `workflow_result_mode`

Keep this bounded: the goal is to prove no accidental global hook was added, not to exhaustively test every output producer.

- [x] **Step 3: Run the focused tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k "precedence or /new or pause or resume or inspection or report or case or non-troubleshooting" -v
```

Expected: FAIL because precedence and troubleshooting-only scope are not yet implemented.

- [x] **Step 4: Implement precedence and scope guards**

Update `nanobot/agent/loop.py` to:

- preserve the current order where session hard controls and target-expansion gates run before result-mode controls
- keep `pause`, `resume`, `change_focus`, and `narrow_scope` ahead of result-mode when a single turn is ambiguous
- restrict result-mode recognition and output shaping to troubleshooting flows only

Do not add a global conversation mode.

- [x] **Step 5: Run the focused tests to verify pass**

Run:

```bash
python3 -m pytest tests/test_agentloop_troubleshooting_flow.py -k "precedence or /new or pause or resume or inspection or report or case or non-troubleshooting" -v
```

Expected: PASS

- [x] **Step 6: Commit**

```bash
git add nanobot/agent/loop.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: enforce evidence-first troubleshooting precedence"
```

## Chunk 3: Runtime Context And Output Reshaping

### Task 3: Add failing tests for evidence-first conclusion shaping

**Files:**
- Modify: `tests/test_agentloop_investigation.py`
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Modify: `nanobot/agent/loop.py`

- [x] **Step 1: Write the failing runtime-context tests**

Add tests that prove `workflow_result_mode == "evidence_first"` contributes bounded troubleshooting-only runtime context without altering investigation tool execution.

At minimum assert:

- the runtime context is injected for troubleshooting turns while the mode is active
- the context text explicitly says result shaping changes but investigation choice remains judgment-based

- [x] **Step 2: Write the failing output-shaping tests**

Add integration-style tests around `_run_agent_loop(...)` or `process_direct(...)` proving:

- evidence-first replies contain evidence/facts before any tendency statement
- when the model returns strong conclusions such as `根因已确认，就是日志轮转失败。`, `问题已经定位到 node-a。`, or `可以确定就是服务配置错误。`, the final user-visible output is downgraded to `当前倾向` style wording
- if the original reply lacks uncertainty or next-step language, the final output gets a minimal uncertainty/next-step addition
- if evidence is weak, the output omits `当前倾向` and only returns evidence, uncertainty, and next step

Mock provider outputs directly; do not depend on prompt quality to produce the right shape by accident.

- [x] **Step 3: Add a regression test that investigation capability is not weakened**

Add a test showing that with `workflow_result_mode == "evidence_first"` active:

- investigation still performs the same readonly tool calls it otherwise would
- only the final troubleshooting reply shape changes

- [x] **Step 4: Add a regression test that structured artifact bodies stay unchanged**

Add a test that enables `workflow_result_mode == "evidence_first"` and feeds one concrete structured artifact fixture, such as a known inspection/report/case body payload, through the final-output path. Assert the full body stays byte-for-byte identical, proving the post-processor is scoped to troubleshooting natural-language result replies only.

- [x] **Step 5: Add a regression test that ordinary non-troubleshooting replies stay unchanged**

Add a test that enables `workflow_result_mode == "evidence_first"` and verifies an unrelated non-troubleshooting reply is returned unchanged, proving the post-processor does not behave like a global conversation rewriter.

- [x] **Step 6: Run the focused tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -k "evidence_first or 当前倾向 or 根因已确认 or 定位到 or 可以确定就是 or next step or inspection or report or case" -v
```

Expected: FAIL because runtime-context injection and output rewriting do not yet exist.

- [x] **Step 7: Implement bounded runtime-context and final-output shaping**

Update `nanobot/agent/loop.py` to:

- extend `_build_workflow_runtime_context(...)` with a troubleshooting-only evidence-first hint
- add a small helper that decides whether a reply is a troubleshooting result candidate for reshaping
- add a bounded post-processor that:
  - preserves evidence text
  - downgrades strong conclusion phrases into `当前倾向` wording
  - ensures uncertainty and next-step content exists
  - never rewrites non-troubleshooting responses or structured artifact bodies

Prefer deterministic phrase transforms and small structural additions over a generic rewriter.

- [x] **Step 8: Run the focused tests to verify pass**

Run:

```bash
python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -k "evidence_first or 当前倾向 or 根因已确认 or 定位到 or 可以确定就是 or next step or inspection or report or case" -v
```

Expected: PASS

- [x] **Step 9: Commit**

```bash
git add nanobot/agent/loop.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: shape troubleshooting conclusions with evidence-first mode"
```

## Chunk 4: Acknowledgements, Compound Cases, And Regression Coverage

### Task 4: Add final user-facing feedback and broaden regression protection

**Files:**
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Modify: `tests/test_agentloop_investigation.py`
- Modify: `nanobot/agent/loop.py`

- [x] **Step 1: Write the failing acknowledgement tests**

Add tests that prove enabling and disabling result mode returns concise confirmations such as:

- `后续先按证据收口；如果判断还不够稳，我会先列证据和未确认点。`
- `已解除证据优先收口；后续可直接给出判断。`

Avoid over-specifying punctuation if the wording itself is not the real requirement.

- [x] **Step 2: Write the failing compound-turn tests**

Add tests for one-turn edge cases called out by the spec review:

- a message that contains both `继续` and `先证据后判断` still prioritizes `resume`
- a troubleshooting turn that follows an enabled result mode still uses the mode on output

- [x] **Step 3: Run the broadened regression slice to verify failure**

Run:

```bash
python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -v
```

Expected: FAIL because final acknowledgement copy and compound-turn precedence are not fully implemented.

- [x] **Step 4: Implement bounded acknowledgements and final edge-case handling**

Update `nanobot/agent/loop.py` so that:

- enable/disable result-mode replies are operational and brief
- compound-turn precedence follows the spec without mutating unrelated workflow state
- normal troubleshooting behavior still works unchanged when result mode is absent

- [x] **Step 5: Run the broadened regression slice to verify pass**

Run:

```bash
python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -v
```

Expected: PASS

- [x] **Step 6: Commit**

```bash
git add nanobot/agent/loop.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: finalize evidence-first troubleshooting feedback"
```

## Chunk 5: Final Verification And Plan Sync

### Task 5: Verify the full implementation and sync plan state

**Files:**
- Modify: `docs/superpowers/plans/2026-03-19-troubleshooting-workflow-phase2-evidence-first.md`
- Inspect: `nanobot/agent/loop.py`
- Inspect: `tests/test_agentloop_investigation.py`
- Inspect: `tests/test_agentloop_troubleshooting_flow.py`

- [x] **Step 1: Run the targeted verification suite**

Run:

```bash
python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -v
```

Expected: PASS

- [x] **Step 2: Run one adjacent regression slice if the implementation touched shared flow code**

Run:

```bash
python3 -m pytest tests/test_commands.py -v
```

Expected: PASS, or document clearly if unrelated failures already exist.

- [x] **Step 3: Mark the completed plan checkboxes**

Update this plan file so every completed step is checked off and reflects reality.

- [x] **Step 4: Commit the final plan sync if needed**

```bash
git add docs/superpowers/plans/2026-03-19-troubleshooting-workflow-phase2-evidence-first.md
git commit -m "docs: sync evidence-first troubleshooting plan status"
```
