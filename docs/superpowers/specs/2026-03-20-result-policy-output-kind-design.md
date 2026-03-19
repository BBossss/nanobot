# Result Policy Output Kind Design

**Date:** 2026-03-20
**Status:** Approved for planning
**Owner:** Codex

## Goal

Evolve `nanobot/agent/workflow/result_policy.py` from a single-purpose evidence-first shaper into a stable output-boundary layer that classifies final outputs before deciding whether any shaping is allowed.

The immediate goal is structural: make future troubleshooting outputs, artifact bodies, and derived summaries extend through one explicit decision point instead of accumulating more ad hoc conditionals.

## Problem

The current `result_policy.py` already contains implicit output classification:

- troubleshooting-like natural-language replies are candidates for evidence-first shaping
- structured artifact bodies are exempt
- generic replies are returned unchanged

That works for the current scope, but it does not scale cleanly as HCIGuard grows more output forms such as:

- troubleshooting natural-language summaries
- inspection / report / case bodies
- timeline-like outputs
- root-cause-candidate style outputs
- future controlled result modes beyond `evidence_first`

Without a single output-classification boundary, new artifact types are likely to reintroduce special cases in `result_policy.py` or leak back into `AgentLoop`.

## Design Goals

- Introduce one explicit output-classification boundary inside `result_policy.py`
- Preserve current visible behavior for evidence-first shaping
- Keep structured artifact bodies protected from accidental rewriting
- Create a stable extension point for future output kinds
- Avoid reintroducing business-specific branching into `AgentLoop`

## Non-Goals

- No new workflow result mode in this change
- No timeline or root-cause-candidate behavior expansion yet
- No output schema redesign for case/report/inspection artifacts
- No new dataclass or enum requirement if simple string kinds are sufficient

## Recommended Approach

Add a first-class `output kind` classification step inside `result_policy.py`, then dispatch shaping behavior based on that classification.

This should be done in two phases:

1. introduce explicit output kinds while preserving current behavior
2. later hang additional artifact types on the same boundary

This spec covers phase 1 and prepares phase 2.

## Output Kind Layer

`result_policy.py` should gain a centralized classifier such as:

- `classify_output_kind(...) -> str`

Initial kinds:

- `troubleshooting_reply`
- `inspection_artifact`
- `report_artifact`
- `case_artifact`
- `timeline_artifact`
- `root_cause_candidate`
- `generic_reply`

The implementation may use string literals rather than enums for now to keep the change lightweight and consistent with the current style.

## Classification Rules

Classification should use repository evidence already available at the shaping boundary:

- `user_content`
- `final_content`
- optional `messages`

### `troubleshooting_reply`

Use for natural-language troubleshooting conclusions, including markdown troubleshooting summaries that are still intended as user-facing reasoning output.

This is the only kind that should currently remain eligible for evidence-first shaping.

### `inspection_artifact`

Use for content that clearly represents inspection artifact output.

This should remain byte-for-byte unchanged.

### `report_artifact`

Use for structured report-like bodies, including plain markdown reports that are intended as stable artifacts rather than conversational replies.

This should remain unchanged.

### `case_artifact`

Use for structured case bodies or case-export-like content.

This should remain unchanged.

### `timeline_artifact`

Reserve this kind now even if current behavior is “leave unchanged”.

The point is to give timeline-like outputs an explicit landing zone instead of forcing them to masquerade as either troubleshooting replies or generic text.

### `root_cause_candidate`

Reserve this kind now for future candidate-style outputs.

For phase 1 it should default to unchanged unless existing behavior already requires otherwise.

### `generic_reply`

Everything that is neither troubleshooting reply nor recognized artifact should land here and remain unchanged.

## Dispatch Layer

`shape_evidence_first_result(...)` should stop doing implicit classification inline.

Instead it should:

1. classify the output
2. check whether the current result mode applies
3. dispatch by output kind

For phase 1, dispatch rules are:

- `troubleshooting_reply`: apply current evidence-first logic
- `inspection_artifact`: unchanged
- `report_artifact`: unchanged
- `case_artifact`: unchanged
- `timeline_artifact`: unchanged
- `root_cause_candidate`: unchanged
- `generic_reply`: unchanged

This preserves current behavior while making future expansions explicit.

## Relationship To Existing Helpers

Existing helpers should be reinterpreted under the new structure rather than left as parallel classification systems.

### `looks_like_structured_artifact_body(...)`

This should no longer be the final gate by itself.

Instead it becomes one source of evidence for classifying:

- `inspection_artifact`
- `report_artifact`
- `case_artifact`

### `is_troubleshooting_result_candidate(...)`

This should stop serving as the top-level shaping gate.

Its responsibilities should be split:

- one part helps classify `troubleshooting_reply`
- one part helps detect strong-conclusion / tendency signals inside troubleshooting content

### strong-conclusion downgrade helpers

These remain relevant, but only inside the `troubleshooting_reply` branch.

## Why This Helps

This design changes the main future question from:

"Should I add one more exception to the evidence-first shaping logic?"

to:

"What output kind is this, and what shaping policy is allowed for that kind?"

That is a cleaner long-term boundary. It keeps:

- `AgentLoop` unaware of output categories
- artifact-protection rules centralized
- future output kinds extensible without reopening core orchestration flow

## Phased Rollout

### Phase A: Structural introduction

Scope:

- introduce `classify_output_kind(...)`
- route current evidence-first shaping through classification
- preserve visible behavior

Success criteria:

- existing evidence-first tests stay green
- existing artifact-bypass tests stay green
- no user-visible behavior changes beyond internal restructuring

### Phase B: Extension landing zones

Scope:

- refine `timeline_artifact`
- refine `root_cause_candidate`
- add tests for those kinds
- define whether future result modes can apply to them

Success criteria:

- new output forms gain explicit stable kinds
- no new ad hoc shaping conditions are needed in `AgentLoop`

## Testing Strategy

Phase A should add focused classification and dispatch tests without removing current regression coverage.

Required tests:

- troubleshooting natural-language reply classifies as `troubleshooting_reply`
- structured inspection/report/case bodies classify as artifact kinds
- generic unrelated reply classifies as `generic_reply`
- evidence-first still shapes only `troubleshooting_reply`
- structured artifacts still remain unchanged
- plain markdown troubleshooting summaries still remain shapeable

Existing evidence-first tests should remain the primary behavioral guardrail.

## Risks

### Misclassification risk

If the new classifier is too broad, artifact bodies could get reshaped accidentally.

Mitigation:

- keep artifact rules conservative
- keep current artifact-bypass regressions
- add explicit classification tests

### Over-modeling too early

If this becomes a large type system now, the code gets heavier without clear gain.

Mitigation:

- use simple string kinds first
- no enum/dataclass requirement in phase 1

### Hidden behavior changes

If classification and shaping are changed in the same step without clear tests, behavior drift becomes hard to diagnose.

Mitigation:

- phase A is explicitly behavior-preserving
- classify first, then dispatch, without adding new shaping rules yet

## Success Criteria

This change is successful if:

- `result_policy.py` gains a single explicit output-classification boundary
- evidence-first shaping behavior stays unchanged for current troubleshooting replies
- artifact outputs remain untouched
- future output forms have an obvious extension point that does not require growing `AgentLoop`
