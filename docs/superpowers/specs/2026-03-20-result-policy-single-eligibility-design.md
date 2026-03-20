# Result Policy Single Eligibility Design

**Date:** 2026-03-20
**Status:** Approved for planning
**Owner:** Codex

## Goal

Collapse evidence-first rewrite eligibility in `nanobot/agent/workflow/result_policy.py` onto the same output-kind boundary already introduced in Phase A.

The outcome should be one semantic decision line:

- classify the output kind
- decide whether that kind is rewrite-eligible
- apply existing troubleshooting shaping only for eligible kinds

This change should preserve current user-visible behavior.

## Problem

Phase A introduced `classify_output_kind(...)` and routed `shape_evidence_first_result(...)` through output kinds, but `result_policy.py` still carries a second semantic gate in `is_troubleshooting_result_candidate(...)`.

Today that means rewrite eligibility is split across two heuristics:

- output classification says what the reply is
- candidate detection separately says whether the reply may be rewritten

That duplication is manageable while only `troubleshooting_reply` is rewriteable, but it creates long-term drift risk:

- future edits can change classification without updating rewrite eligibility
- artifact shapes can be correctly classified but still depend on a second gate staying aligned
- future output kinds such as `timeline_artifact` and `root_cause_candidate` would otherwise need yet another eligibility rule path

The code already showed this pressure during Phase A review, where classification and bypass behavior had to be reasoned about separately.

## Design Goals

- Keep one semantic source of truth for rewrite eligibility
- Preserve current evidence-first behavior exactly
- Keep `AgentLoop` unchanged
- Retain `is_troubleshooting_result_candidate(...)` as a compatibility wrapper for now
- Make future output-kind expansion depend on one contract instead of parallel heuristics

## Non-Goals

- No new workflow result mode
- No new output kinds
- No behavior expansion for `timeline_artifact` or `root_cause_candidate`
- No change to strong-conclusion downgrade wording
- No broad refactor outside `result_policy.py` and its focused tests

## Recommended Approach

Introduce an explicit internal eligibility helper, driven only by output kind, and route both the shaper and the compatibility wrapper through it.

The core structure should become:

1. `classify_output_kind(...) -> str`
2. `is_output_kind_rewrite_eligible(kind: str) -> bool`
3. `shape_evidence_first_result(...)` uses `kind` plus eligibility helper
4. `is_troubleshooting_result_candidate(...)` becomes a thin compatibility wrapper that derives kind from content and returns whether that kind is eligible

This keeps the public surface stable while removing the second semantic decision system.

## Eligibility Contract

For this phase, rewrite eligibility remains intentionally narrow:

- `troubleshooting_reply`: eligible
- `inspection_artifact`: ineligible
- `report_artifact`: ineligible
- `case_artifact`: ineligible
- `timeline_artifact`: ineligible
- `root_cause_candidate`: ineligible
- `generic_reply`: ineligible

This means the behavioral contract becomes:

"If and only if the output classifies as `troubleshooting_reply`, evidence-first shaping may rewrite it."

That is the contract future phases should extend, not bypass.

## Compatibility Strategy

`is_troubleshooting_result_candidate(...)` should remain in place for now because:

- existing tests already reference it directly
- keeping the name avoids unnecessary churn in nearby code and tests
- the function can still express legacy intent while no longer owning its own eligibility semantics

However, it should become a compatibility shell, not a second policy engine.

Its signature should expand to accept optional context:

- `is_troubleshooting_result_candidate(content, user_content=None, messages=None)`

It should:

- accept content as it does today
- use the same classification path as `shape_evidence_first_result(...)` whenever `user_content` is available
- return the result of `is_output_kind_rewrite_eligible(...)`

When `user_content` is unavailable, the wrapper may use a narrow content-only fallback classifier, but that fallback must:

- exist only to support compatibility callers that do not have request context
- return output kinds, not direct rewrite decisions
- flow through the same `kind -> eligibility` contract as the main path
- stay conservative for ambiguous content

This means there are still two inference modes, but only one eligibility contract.

## Implementation Shape

Inside `result_policy.py`:

- keep existing output-kind constants
- keep existing classification helpers where still useful
- add one small helper for eligibility by kind
- add one content-only helper only if needed to support the compatibility wrapper cleanly
- avoid large restructuring of strong-conclusion downgrade helpers

Inside `shape_evidence_first_result(...)`:

- classify once
- return unchanged when kind is not rewrite-eligible
- preserve existing troubleshooting rewrite logic under the eligible branch

Inside `is_troubleshooting_result_candidate(...)`:

- remove direct artifact/troubleshooting heuristics as policy logic
- when context is present, delegate to the same classification path used by the shaper
- when context is absent, use the compatibility fallback classifier and still delegate through the same eligibility contract

## Testing Strategy

This phase is behavior-preserving, so tests should emphasize unchanged behavior rather than new product behavior.

Required coverage:

- focused policy tests showing `is_troubleshooting_result_candidate(...)` agrees with output-kind eligibility for:
  - troubleshooting reply
  - inspection artifact
  - report artifact
  - case artifact
  - timeline artifact
  - root-cause candidate artifact
  - generic reply
- focused policy tests showing the compatibility wrapper behaves correctly both:
  - with `user_content` present
  - without `user_content`, using the content-only fallback path
- existing evidence-first shaping tests stay green
- existing artifact-bypass tests stay green
- existing markdown troubleshooting summary shaping tests stay green

The policy-level tests should verify the compatibility wrapper still returns the same practical answers while no longer relying on an independent artifact gate.

## Risks

### Hidden behavior drift

If the wrapper loses subtle behavior while being simplified, ordinary troubleshooting replies could stop being rewritten.

Mitigation:

- add focused wrapper-alignment tests first
- rerun existing `result_policy` and `AgentLoop` evidence-first regressions

### Accidental over-coupling to `user_content`

The wrapper currently accepts only `content`. If the new implementation quietly depends on `user_content`, behavior could drift or become surprising.

Mitigation:

- define the wrapper signature to accept optional context explicitly
- require parity tests for both contextual and content-only calls
- if a content-only classifier is needed, keep it narrow and eligibility-focused

### Premature architecture growth

This is a cleanup step, not a new type system.

Mitigation:

- introduce one small eligibility helper only
- keep the rest of the code shape stable

## Success Criteria

- `result_policy.py` has only one semantic eligibility contract for evidence-first rewriting
- `is_troubleshooting_result_candidate(...)` remains available but no longer acts as an independent policy engine
- current user-visible evidence-first behavior remains unchanged
- focused policy tests and existing regressions remain green
