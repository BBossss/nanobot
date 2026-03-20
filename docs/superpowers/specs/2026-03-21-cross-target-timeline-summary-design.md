# Cross-Target Timeline Summary Design

**Date:** 2026-03-21
**Status:** Draft for review
**Owner:** Codex

## Goal

Make multi-target troubleshooting replies cite cross-target timeline conclusions directly in the final troubleshooting answer, while keeping the full `timeline_artifact` internal and reusable for later report/case consumers.

This phase specifically targets the troubleshooting reply / evidence-first output path. It does not change the existing timeline artifact schema or expose raw timeline artifact Markdown to the user by default.

## Problem

HCIGuard now has a stable cross-target `timeline_artifact` builder and a conservative multi-target integration helper. That gives the system structured incident chronology across targets, but the final troubleshooting reply still does not consume that chronology.

Current behavior has a gap:

- the system can build a structured cross-target timeline internally
- the user-facing final reply still depends only on the model's natural-language conclusion
- evidence-first shaping can preserve or rewrite conclusions, but it does not inject any structured cross-target chronology

This means a valuable incident signal is available but often invisible in the final answer.

## Desired Outcome

When a troubleshooting turn uses log-oriented multi-target evidence and a cross-target timeline is available, the final troubleshooting reply should include a short timeline conclusion inside the existing evidence section.

Example shape:

`时间线补充：最早在 10:21:03 由 node-a 出现超时，node-b 随后近同时出现同类异常；10:22:11 起 node-c 出现本地 permission denied。`

This should help the user understand:

- which target showed the earliest signal
- whether the issue was shared or near-shared across targets
- whether a later local-only event appeared on another target

## Non-Goals

- No direct rendering of full timeline artifact Markdown into the default troubleshooting reply
- No new artifact kind
- No timeline parsing from free-form reply text or presentation Markdown
- No report/case integration in this phase
- No root-cause candidate generation changes in this phase
- No new UI section or separate "timeline" block in the final troubleshooting reply

## Design Principles

- Keep `timeline_artifact` as the internal structured boundary
- Reuse existing multi-target aggregation objects instead of reparsing output text
- Keep timeline summarization narrow, deterministic, and log-only
- Keep result shaping logic presentation-focused, not chronology-computation-focused
- Avoid duplicate or noisy insertion into final replies

## Recommended Approach

Add one explicit cross-target timeline summary helper on the structured multi-target aggregation object, then let the troubleshooting result shaping path consume that summary when appropriate.

Why this approach:

- it preserves the existing artifact boundary
- it keeps chronology logic near the aggregation/timeline layer where the structured data already exists
- it avoids re-parsing rendered Markdown in `result_policy`
- it creates a reusable summary seam that later report/case flows can also consume if needed

## Data Flow

Expected flow:

1. log-oriented multi-target troubleshooting runs through the existing aggregation path
2. `MultiTargetAggregation` can already build a cross-target `timeline_artifact`
3. a new helper derives a short natural-language summary from that artifact
4. `AgentLoop` carries the current-turn structured multi-target result forward to final result shaping
5. `result_policy.shape_evidence_first_result(...)` inserts the summary into the evidence section when the final output is still a troubleshooting reply

## Architecture Boundaries

### Multi-Target Aggregation Layer

`nanobot/agent/multi_target.py` remains the structured integration point.

The aggregation object should expose a helper such as:

- `build_cross_target_timeline_summary(...)`

This helper should:

- return `None` for non-log tools
- return `None` if no timeline artifact exists
- return `None` if the artifact has no admitted events
- otherwise return one bounded summary string

This helper should internally reuse:

- `build_cross_target_timeline_artifact(...)`

It should not duplicate timeline grouping logic outside the artifact builder.

### Agent Loop Layer

`AgentLoop` should remain a coordinator, not a chronology engine.

It may store the current-turn multi-target aggregation or derived timeline summary in a bounded way so the final result shaping path can consume it. The loop should not compute shared / near-shared / local logic itself.

### Result Policy Layer

`nanobot/agent/workflow/result_policy.py` should stay focused on output shaping, not evidence correlation.

It may:

- detect whether the current reply is rewrite-eligible
- decide whether the timeline summary should be inserted
- place the summary into the visible evidence section

It must not:

- rebuild timeline events from tool text
- re-run cross-target grouping
- parse raw timeline artifact Markdown to reconstruct incident logic

## Summary Content Rules

The summary should stay short and operator-facing.

Default content should include:

- earliest timestamp
- earliest target
- whether the first cluster was `shared` or `near_shared`
- later local-only event if present

Default content should not include:

- every event in the timeline artifact
- raw evidence snippets
- tool invocation details unless necessary later
- broad speculative interpretation

## Summary Rendering Rules

Recommended wording style:

- concise Chinese troubleshooting prose
- one or two short sentences maximum
- no new heading or dedicated section
- prefixed with `时间线补充：`

Example patterns:

- shared:
  - `时间线补充：10:21:03 起 node-a,node-b,node-c 同时出现同类超时。`
- near-shared:
  - `时间线补充：最早在 10:21:03 由 node-a 出现超时，node-b,node-c 随后近同时出现同类异常。`
- shared plus later local:
  - `时间线补充：最早在 10:21:03 由 node-a 出现超时，node-b 随后近同时出现同类异常；10:22:11 起 node-c 出现本地 permission denied。`

The exact wording can remain conservative in v1 as long as it is stable enough for tests.

## Insertion Rules

The timeline summary should be inserted only when all of the following are true:

- current turn is a troubleshooting-like turn
- final output kind is `troubleshooting_reply`
- evidence-first mode is active, or the selected final reply shaping path explicitly supports this insertion point
- current turn produced a multi-target aggregation from a log-oriented tool
- a non-empty cross-target timeline summary is available

The timeline summary should not be inserted when:

- output is already `timeline_artifact`
- output is `report_artifact`, `case_artifact`, or `inspection_artifact`
- tool family is non-log (`service_status`, `process_snapshot`, etc.)
- scope is effectively single-target
- no timestamped cross-target timeline exists

## Duplication Guard

This phase should remain conservative about duplication.

If the final troubleshooting reply already appears to contain a highly similar explicit timeline statement, the system should avoid adding another `时间线补充：...` line.

The first version does not need deep semantic deduplication. A bounded string-level guard is acceptable if it is stable and easy to reason about.

## Failure Handling

If timeline summary generation fails or returns `None`:

- final troubleshooting reply should continue unchanged
- no new error should be exposed to the user
- artifact behavior should remain unchanged

This keeps the summary path opportunistic rather than mandatory.

## Testing Strategy

### Multi-Target Aggregation Tests

Add focused tests proving:

- shared plus local timeline artifacts produce the expected summary
- near-shared clusters produce the expected summary
- no timestamped events returns `None`
- non-log tools return `None`

### Result Policy Tests

Add focused tests proving:

- evidence-first troubleshooting shaping inserts the timeline summary into evidence text
- existing timeline/report/case artifact outputs remain untouched
- no summary is inserted when the reply is not rewrite-eligible
- no summary is inserted for non-log or single-target cases

### Agent Loop / End-to-End Slice

Add one focused troubleshooting flow test proving:

- multi-target log evidence can produce a final troubleshooting reply containing the inserted timeline summary
- the reply still remains a troubleshooting reply rather than becoming a timeline artifact

## File Impact

Expected files for implementation:

- Modify: `nanobot/agent/multi_target.py`
- Modify: `nanobot/agent/loop.py`
- Modify: `nanobot/agent/workflow/result_policy.py`
- Modify: `tests/test_multi_target_troubleshooting.py`
- Modify: `tests/test_result_policy.py`
- Modify: `tests/test_agentloop_investigation.py` or `tests/test_agentloop_troubleshooting_flow.py`

## Open Questions Resolved

- User-visible form:
  - do not render full timeline artifact in final reply
  - do render a short summary inside evidence text
- Preferred insertion style:
  - fold into `已确认事实`, not a dedicated section
- Preferred summary richness:
  - include key conclusion plus key timestamps

## Recommendation

Proceed with a narrow implementation:

- add a summary helper on `MultiTargetAggregation`
- pass the summary through the final troubleshooting shaping path
- only inject it for rewrite-eligible troubleshooting replies
- keep all full artifact behavior unchanged

This gives HCIGuard a stronger operator-facing final answer without weakening the internal artifact boundary needed for later report/case work.
