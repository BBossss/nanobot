# Cross-Target Timeline Design

**Date:** 2026-03-20
**Status:** Draft for review
**Owner:** Codex

## Goal

Add a first stable cross-target incident timeline for HCIGuard so multi-target troubleshooting can explain how evidence appeared across nodes over time, not only compare node-level summaries.

The first phase should:

- focus only on log-oriented evidence from `search_log` and `read_log_tail`
- build a stable cross-target `timeline_artifact`
- keep strict timestamp-only admission rules
- let troubleshooting/report flows consume that artifact later without re-parsing summary text

## Problem

HCIGuard now has two important foundations:

- bounded multi-target evidence aggregation
- a stable single-artifact boundary for `timeline_artifact`

These solve adjacent parts of the problem, but they do not yet create a true cross-target incident timeline.

Today the system can:

- fan out readonly troubleshooting checks across multiple targets
- group shared/local findings across those targets
- build timeline-like output from log evidence

But it still lacks a stable answer to this question:

"How do we express one incident timeline across multiple targets, with explicit evidence and target boundaries?"

Without that layer, multi-target troubleshooting still has a gap:

- grouped findings tell us what is shared vs local
- per-target evidence tells us what each node saw
- but the system does not yet turn that into one reusable cross-target incident timeline artifact

That makes later phases harder:

- troubleshooting output must improvise event ordering
- report generation cannot rely on one stable cross-target timeline contract
- root-cause candidate work would still need to derive chronology from intermediate text

## Design Goals

- Reuse existing multi-target aggregation and timeline extraction foundations
- Produce one stable cross-target timeline artifact
- Keep strict timestamped-evidence admission rules from the existing timeline work
- Preserve target identity inside the timeline
- Support both shared/near-concurrent evidence and local-only evidence in one incident view
- Keep the first version narrow and explainable

## Non-Goals

- No automatic root-cause candidate generation in this phase
- No support for non-log evidence as the main timeline body in this phase
- No broad event-correlation engine across all tool families
- No fuzzy time inference for evidence without explicit timestamps
- No redesign of the existing target confirmation or aggregation flow

## Scope

This phase covers only evidence originating from:

- `search_log`
- `read_log_tail`

The artifact should be built from multi-target log evidence that already passed through the bounded aggregation path.

This phase does not pull `service_status` or `process_snapshot` into the main timeline body.

## Product Positioning

The cross-target timeline is an incident artifact, not just a nicer summary section.

It should help answer:

- which target showed the earliest timestamped evidence
- whether multiple targets showed the same event at the same time or nearly the same time
- whether a later event appears to be a spread, escalation, or recovery signal
- which evidence remained local to one target

It should not answer:

- what the final root cause is
- what remediation should be taken
- what the agent did internally

## Design Summary

Introduce a stable cross-target timeline builder above the current multi-target aggregation output.

Expected flow:

1. multi-target log-oriented troubleshooting collects per-target raw results
2. the system reuses existing timestamped event extraction from those raw results
3. cross-target timeline logic groups and orders those events into one incident timeline artifact
4. the artifact can later be surfaced directly in troubleshooting or report output

The key design point is:

- aggregation remains responsible for grouping evidence by target/signature
- cross-target timeline remains responsible for ordering timestamped incident evidence across targets

## Artifact Boundary

The output of this phase should still be a `timeline_artifact`, not a new artifact kind.

What changes is the evidence origin:

- instead of a single-target or generic timeline
- the artifact now represents a cross-target incident timeline built from multiple targets

This keeps downstream consumers aligned with the existing artifact taxonomy while strengthening the meaning of timeline output in multi-target troubleshooting.

## Input Contract

The builder should work from structured multi-target log evidence, not from arbitrary free-form Markdown.

The minimal expected input is:

- tool name (`search_log` or `read_log_tail`)
- ordered per-target raw results
- extracted timestamped log events with target identity preserved

If the current multi-target aggregation object already preserves enough raw per-target data, the cross-target timeline builder should consume that structure directly.

## Timeline Admission Rules

The existing strict timeline rules remain in force:

- only evidence with explicit timestamps may enter the main timeline body
- every admitted event must keep both target identity and supporting evidence
- if evidence cannot be assigned a clear timestamp, it must not enter the timeline body

This phase may include a coverage or missing-evidence note, but it must not invent ordering for untimestamped data.

## Cross-Target Event Model

The first cross-target event model should remain close to the existing timeline artifact event shape, but it needs one more semantic distinction: whether an event is shared across targets or local to one target.

Recommended event-level fields:

- `timestamp_normalized`
- `timestamp_raw`
- `event`
- `evidence`
- `target`
- `source`
- `scope`

Field intent:

- `timestamp_normalized`: stable cross-target ordering key
- `timestamp_raw`: original time text
- `event`: concise human-readable event summary
- `evidence`: supporting evidence snippet
- `target`: concrete target ID or host
- `source`: evidence source such as `search_log` or `read_log_tail`
- `scope`: lightweight event scope marker such as `shared`, `near_shared`, or `local`

The first phase should keep the scope vocabulary small and stable.

## Scope Semantics

Version 1 should support three coarse scope values:

- `shared`: the same or clearly equivalent evidence appears on multiple targets at the same timestamp bucket
- `near_shared`: similar evidence appears on multiple targets close in time, but not exactly together
- `local`: evidence is only present on one target in the timeline body

This phase should stay conservative:

- if equivalence is unclear, prefer `local`
- if timing relation is weak, do not force `near_shared`

## Grouping Rules

Cross-target timeline grouping should remain evidence-driven.

Recommended rules:

- use current log event extraction and normalization rather than inventing a new parser
- only group events when timestamp and evidence pattern are close enough to justify shared interpretation
- preserve separate local entries when evidence differs materially between targets

This means the timeline may contain:

- a shared cross-target event
- a local event that appears before the shared event
- a later local recovery event

That is acceptable and useful.

## Artifact-Level Metadata

The cross-target timeline artifact should keep the current artifact-level metadata when available:

- `incident`
- `target`
- `window_start`
- `window_end`
- `coverage_note`
- `events`

For cross-target output:

- `target` may represent a target group, a comma-separated scope, or another compact scope label
- `coverage_note` should be used to clarify exclusions such as untimestamped evidence not entering the main timeline

The exact string format can stay conservative in v1.

## Markdown Output Shape

The first stable Markdown output should remain aligned with the existing timeline artifact style:

```md
# Timeline

Incident: storage timeout incident
Target: node-a,node-b,node-c
Window: 2026-03-20T10:21:03Z to 2026-03-20T10:28:41Z

## Events

- Timestamp: 2026-03-20T10:21:03Z
  Event: shared storage backend timeout appeared on node-a and node-b
  Evidence: /sf/log/app.log `timeout while connecting to storage backend`
  Target: node-a,node-b
  Source: search_log

- Timestamp: 2026-03-20T10:22:11Z
  Event: local permission-denied write failure appeared on node-c
  Evidence: /sf/log/app.log `permission denied writing to storage backend`
  Target: node-c
  Source: search_log

## Coverage Note

Only evidence with explicit timestamps is included in this timeline.
```

The first phase does not need a radically new Markdown format. It should strengthen the semantics of the event content and target coverage.

## Relationship To Existing Code

This design should build on:

- multi-target aggregation in `nanobot/agent/multi_target.py`
- existing log event extraction and timeline formatting in `nanobot/agent/timeline.py`
- current `timeline_artifact` result-policy boundary

The intended layering is:

- aggregation organizes multi-target evidence
- cross-target timeline logic orders timestamped evidence across targets
- timeline formatting renders the final artifact

This should avoid collapsing all responsibilities into one module.

## Testing Goals

The first implementation phase should prove:

- cross-target timeline is built only from the two supported log tools
- shared / near-shared / local cross-target events are rendered deterministically
- target identity is preserved in each emitted event
- untimestamped evidence stays out of the main timeline body
- output still classifies as a valid `timeline_artifact`

## Acceptance Criteria

This design is successful when:

- multi-target log evidence can produce one stable cross-target `timeline_artifact`
- timeline events preserve timestamps, target identity, and source evidence
- troubleshooting/report flows can consume the artifact without re-parsing grouped summary Markdown
- the phase stays narrow and does not absorb candidate/root-cause work

## Why This Phase Comes After Aggregation

Cross-target timeline should come after multi-target aggregation because it needs a stable target-aware evidence contract to build from.

Without that aggregation layer:

- timeline logic would need to infer structure from rendered summary text
- shared vs local evidence boundaries would be inconsistent
- later consumers would not know whether they were reading raw evidence or already-shaped prose

With aggregation in place, cross-target timeline becomes a focused, incident-oriented next step rather than another formatting patch.
