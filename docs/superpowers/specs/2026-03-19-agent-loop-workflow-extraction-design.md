# AgentLoop Workflow Extraction Design

**Date:** 2026-03-19
**Status:** Approved for planning
**Owner:** Codex

## Goal

Refactor `AgentLoop` so it stays the orchestration entrypoint, while workflow rules and troubleshooting result shaping move into focused modules under `nanobot/agent/workflow/`.

The primary requirement is to reduce structural complexity without weakening troubleshooting capability or changing the current external behavior.

## Problem

`nanobot/agent/loop.py` currently holds several different responsibilities at once:

- session-level message orchestration
- troubleshooting workflow control parsing and precedence
- multi-target confirmation-gated targeting behavior
- troubleshooting feedback rendering
- evidence-first result shaping
- case auto-record integration

This has produced a file that is still behaviorally correct, but increasingly fragile. The recent `继续` conflict with exec confirmation was a concrete signal that control precedence is becoming harder to reason about when unrelated concerns share the same control surface.

## Design Goals

- Keep `AgentLoop` as the runtime orchestrator.
- Preserve current session metadata keys and semantics.
- Preserve current user-visible behavior unless a change is explicitly required for correctness.
- Extract workflow-specific logic into focused files that can be read and tested independently.
- Avoid introducing a new workflow state object in this refactor.
- Keep troubleshooting capability at least as strong as it is now.

## Non-Goals

- No redesign of the agent execution loop itself.
- No workflow engine or planner abstraction.
- No session schema migration.
- No case/inspection policy redesign in this refactor.
- No broad naming cleanup unrelated to the extraction.

## Recommended Approach

Adopt a four-module extraction under `nanobot/agent/workflow/` and keep `AgentLoop` as the caller.

### Why this approach

This is the best balance between under-refactoring and over-design:

- Smaller than a full state-model rewrite
- More meaningful than extracting only one or two helpers
- Leaves the execution path recognizable
- Creates stable extension points for later workflow phases

## New Module Layout

Create:

- `nanobot/agent/workflow/__init__.py`
- `nanobot/agent/workflow/control.py`
- `nanobot/agent/workflow/targeting.py`
- `nanobot/agent/workflow/result_policy.py`
- `nanobot/agent/workflow/feedback.py`

### `control.py`

Responsibility:

- troubleshooting control phrase recognition
- evidence-first control phrase recognition
- troubleshooting-context gating for result-mode controls
- workflow control precedence within the control layer
- workflow session metadata reads/writes for:
  - `workflow_paused`
  - `workflow_focus_hint`
  - `workflow_scope_constraints`
  - `workflow_result_mode`
  - `workflow_result_mode_reason`
  - `workflow_last_control_input`

This module should own the bounded phrase matching helpers and troubleshooting-content detection helpers that are currently embedded in `AgentLoop`.

### `targeting.py`

Responsibility:

- pending target-expansion confirmation gate
- confirmed multi-target scope lifecycle
- scope reuse checks
- forbid-multi-target checks
- confirmed-scope progress text

This module owns session metadata related to:

- `pending_target_resolution`
- `resolved_target_ids`
- `resolved_targets`
- `resolution_reason`
- `expansion_confirmed`
- `expansion_skip_reprompt_once`

It must preserve the existing precedence rule: target expansion confirmation handling runs before workflow control parsing.

### `result_policy.py`

Responsibility:

- workflow runtime context construction for result-mode effects
- evidence-first final-result shaping
- troubleshooting-result candidate detection
- strong-conclusion downgrading
- weak-evidence suppression of tendency output
- uncertainty and next-step completion
- structured artifact body bypass

This module must continue to enforce the existing rule that evidence-first changes only the result presentation, not investigation behavior.

### `feedback.py`

Responsibility:

- progress action text
- progress reason text
- heartbeat text
- process-summary text
- multi-target feedback text variants

This module is presentation-only. It must not mutate session state or influence execution decisions.

## AgentLoop After Refactor

`AgentLoop` remains responsible for:

- handling `/new` and `/help`
- creating or loading sessions
- building message context
- invoking `_run_agent_loop(...)`
- executing tools and provider calls
- saving turns and sessions
- calling case auto-recording
- returning outbound messages

`AgentLoop` should stop owning detailed workflow parsing and text-shaping logic directly.

## Target Control Flow

The intended `_process_message(...)` shape after extraction is:

1. handle slash commands
2. call target-expansion gate
3. call workflow-control handler
4. short-circuit paused sessions
5. build context and inject workflow runtime context
6. run investigation / tool loop
7. shape final result through result policy
8. save turn, save session, maybe record case, return response

This preserves the current runtime order while moving detailed rules out of `AgentLoop`.

## Interface Shape

Prefer function-style modules over new classes for this refactor.

### `control.py`

Expected public functions:

- `parse_troubleshooting_control_intent(content: str) -> str | None`
- `parse_result_mode_control_intent(content: str) -> str | None`
- `should_consider_result_mode_control(session: Session, content: str) -> bool`
- `handle_workflow_control(session: Session, content: str) -> str | None`

Internal helpers may include:

- troubleshooting-content detection
- bounded phrase matching
- last-user / last-assistant turn checks

### `targeting.py`

Expected public functions:

- `handle_target_expansion_gate(...) -> str | None`
- `workflow_allows_confirmed_multi_target(session: Session | None) -> bool`
- `workflow_forbids_multi_target(session: Session) -> bool`
- `build_confirmed_scope_progress(session: Session) -> str | None`
- `clear_confirmed_target_scope(session: Session, *, skip_reprompt_once: bool) -> None`

The final signature for `handle_target_expansion_gate(...)` should pass only the dependencies it actually needs, not the whole `AgentLoop`, unless narrowing the parameter surface would create unnecessary churn in this first pass.

### `result_policy.py`

Expected public functions:

- `build_workflow_runtime_context(session: Session, content: str | None = None) -> str | None`
- `shape_evidence_first_result(session: Session | None, user_content: str, final_content: str | None, messages: list[dict[str, Any]] | None = None) -> str | None`

### `feedback.py`

Expected public functions:

- `render_progress_action(name: str, arguments: dict[str, Any], *, multi_target_total: int) -> str`
- `render_progress_reason(bucket: str, *, multi_target_total: int) -> str`
- `render_progress_heartbeat(name: str, *, multi_target_total: int) -> str`
- `render_process_summary(investigation: InvestigationState) -> str | None`

## Behavior Preservation Rules

The refactor must preserve these rules:

- target-expansion confirmation still takes precedence over workflow-control parsing
- `pause/resume/change_focus/narrow_scope` behavior remains unchanged
- `evidence_first` still applies only to troubleshooting result shaping
- structured inspection/report/case outputs remain untouched
- troubleshooting investigation strength must not be reduced
- current session metadata keys remain unchanged
- current regression around exec confirmation and `继续` remains fixed

## Testing Strategy

Refactor in small steps with behavior-preserving tests at each stage.

Required coverage:

- existing workflow-control tests remain green
- existing target-expansion precedence tests remain green
- existing evidence-first shaping tests remain green
- existing exec confirmation regression remains green
- extraction-specific smoke tests confirm public helper entrypoints behave identically

Prefer moving tests only when necessary. Existing tests should continue to validate behavior through `AgentLoop`.

## Implementation Sequence

Recommended extraction order:

1. `control.py`
2. `targeting.py`
3. `result_policy.py`
4. `feedback.py`
5. final `AgentLoop` cleanup

This order minimizes risk:

- `control.py` and `targeting.py` isolate the highest-risk precedence logic first
- `result_policy.py` removes dense result-shaping logic second
- `feedback.py` is presentation-only and safest to move last

## Risks

### Precedence regressions

Moving control code can accidentally reorder target confirmation, resume handling, or result-mode parsing.

Mitigation:

- keep existing call order in `_process_message(...)`
- preserve exact regression tests

### Hidden coupling through session metadata

The current logic uses shared metadata keys across multiple helper paths.

Mitigation:

- do not rename keys in this refactor
- do not introduce a second state source

### Over-design

Adding classes or new state abstractions now would increase migration scope without clear payoff.

Mitigation:

- keep modules function-oriented
- keep `AgentLoop` orchestration structure recognizable

## Success Criteria

This refactor is successful if:

- `AgentLoop` becomes materially smaller and easier to scan
- workflow rules move into focused modules with clear ownership
- all current workflow, targeting, and evidence-first tests still pass
- troubleshooting capability and output quality stay unchanged
- future workflow additions can be implemented without growing `loop.py` in the same way again
