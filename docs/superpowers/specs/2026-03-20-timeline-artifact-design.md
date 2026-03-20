# Timeline Artifact Design

**Date:** 2026-03-20
**Status:** Approved for planning
**Owner:** Codex

## Goal

Define a first stable `timeline_artifact` for HCIGuard that represents an incident timeline, not an agent activity log.

The first version should produce an evidence-driven artifact that:

- focuses on incident events
- only includes events with explicit timestamps
- remains protected from evidence-first rewrite shaping
- is readable as Markdown
- also exposes a minimal internal field structure that later phases can reuse for reports, cases, and search

## Problem

The repository already has timeline-related capability, but it does not yet define a stable incident artifact boundary.

Today there are several adjacent pieces:

- log timeline extraction in `nanobot/agent/timeline.py`
- timeline-like output discussed in earlier design docs
- `timeline_artifact` kind reserved in `result_policy.py`

What is still missing is a clear answer to:

"What exact output should count as a stable incident timeline artifact?"

Without that boundary, timeline output risks staying in an awkward middle state:

- some content is just a free-form summary
- some content is a log-derived timeline section inside other output
- the classifier only recognizes timeline in a coarse way
- future report/case integration has no stable artifact contract to target

## Design Goals

- Make `timeline_artifact` a real output form, not only a reserved kind
- Keep the first version strict and trustworthy
- Separate incident events from agent actions
- Keep timeline artifacts byte-for-byte protected from evidence-first rewrite
- Define both a stable Markdown shape and a minimal internal field shape
- Reuse current timeline/log capabilities where possible instead of rebuilding extraction logic

## Non-Goals

- No redesign of `nanobot/agent/timeline.py`
- No broad time parsing overhaul
- No support for events without explicit timestamps in the main timeline
- No “relative time” events in v1
- No root-cause inference or candidate ranking inside the timeline artifact
- No multi-source reconciliation engine in this phase

## Product Positioning

The first `timeline_artifact` is an incident artifact.

It should answer:

- when the incident started to show visible evidence
- how key incident evidence progressed over time
- when recovery evidence appeared

It should not answer:

- what the agent did internally
- what command was run first
- what the final root cause is

Those may reference the timeline later, but they are not the timeline artifact itself.

## Strict Inclusion Rule

Version 1 uses a strict inclusion boundary:

- only events with explicit timestamps may appear in the main timeline
- if the evidence cannot be assigned a clear timestamp, it does not enter the timeline body

This is intentional.

The artifact should prefer omission over invented ordering.

## Dual Representation

The artifact should have two aligned representations.

### External Markdown Artifact

This is the user-facing output and the artifact body that `result_policy.py` recognizes and preserves unchanged.

### Minimal Internal Structure

This is the smallest stable schema needed so future components can reason about timeline entries without re-parsing prose.

The internal structure does not need a new public API yet, but the spec should define the shape now so generation and classification stay aligned.

## Minimal Field Structure

Each timeline event should support the following fields:

- `timestamp`
- `event`
- `evidence`
- `target` optional
- `source` optional

Field intent:

- `timestamp`: the explicit incident/event time carried by the source evidence
- `event`: short human-readable incident event summary
- `evidence`: concrete supporting evidence, ideally including citation-like source text
- `target`: node/host/target when applicable
- `source`: source channel such as log path, tool output, or evidence reference

Version 1 should not require more structure than this.

## Markdown Artifact Shape

The first stable Markdown shape should be conservative and regular.

Recommended layout:

```md
# Timeline

Incident: storage timeout incident
Target: node-a
Window: 2026-03-20T10:21:03Z to 2026-03-20T10:28:41Z

## Events

- Timestamp: 2026-03-20T10:21:03Z
  Event: node-a started reporting storage backend timeout
  Evidence: /var/log/storage.log:120 `timeout while connecting to backend`
  Target: node-a
  Source: search_log

- Timestamp: 2026-03-20T10:21:05Z
  Event: node-b reported the same timeout pattern
  Evidence: /var/log/storage.log:88 `timeout while connecting to backend`
  Target: node-b
  Source: search_log

## Coverage Note

Only evidence with explicit timestamps is included in this timeline.
```

Rules:

- heading must be `# Timeline`
- `## Events` is the canonical event section
- every event entry must include `Timestamp`, `Event`, and `Evidence`
- `Target` and `Source` are optional
- a short `Coverage Note` section is allowed and recommended

## Marker And Classification Rules

`timeline_artifact` classification should become more concrete around this stable shape.

The classifier should recognize timeline artifacts when there is explicit timeline intent, such as:

- heading `# Timeline`
- heading `# Event Timeline`
- frontmatter markers like `kind: timeline`, `type: timeline`, or `output_kind: timeline`

At the same time, it must remain conservative:

- a troubleshooting reply that merely mentions times should not become a timeline artifact
- unordered timestamp mentions without timeline markers should not become a timeline artifact
- relative-time wording without explicit timestamps should not become a timeline artifact

## Relationship To Existing Timeline Code

This design does not replace current log timeline extraction.

Instead, it introduces a stable artifact boundary above it.

Likely relationship in later implementation:

- `nanobot/agent/timeline.py` continues to extract and summarize timestamped evidence
- a new timeline-artifact formatter or policy layer shapes that evidence into the stable Markdown + minimal-field representation
- `result_policy.py` treats the output as `timeline_artifact` and preserves it unchanged

## Evidence Quality Rules

Version 1 should stay evidence-driven:

- every timeline event should be backed by concrete evidence text
- each event should try to preserve source context when available
- if evidence is too vague to anchor the event, the event should not be emitted

This means timeline completeness is secondary to trustworthiness.

## Exclusions

The following should not appear in version 1 timeline artifacts:

- agent command history
- approvals or audit actions
- events without explicit timestamps
- relative-time-only statements such as “after restart” or “later”
- speculative root-cause conclusions
- remediation recommendations

These may appear in reports or cases later, but not in the incident timeline body.

## Result Policy Behavior

`timeline_artifact` should remain ineligible for evidence-first rewrite.

That means:

- `classify_output_kind(...)` should recognize the artifact boundary cleanly
- `shape_evidence_first_result(...)` should return it unchanged
- future result-policy expansion should treat timeline as a stable output form, not as a troubleshooting reply variant

## Testing Strategy

Version 1 should add focused tests at the policy boundary first.

Required coverage:

- a canonical Markdown timeline artifact classifies as `timeline_artifact`
- a frontmatter-marked timeline artifact classifies as `timeline_artifact`
- a troubleshooting reply with timestamp mentions does not classify as `timeline_artifact`
- content without explicit timeline markers does not become timeline artifact just because it contains times
- `shape_evidence_first_result(...)` leaves timeline artifacts unchanged
- timeline artifact examples with `Timestamp/Event/Evidence` structure remain protected from rewrite

If implementation touches timeline generation later, generation-specific tests can be added in a separate phase.

## Risks

### Over-classification

If timeline detection becomes too broad, ordinary troubleshooting summaries could stop being shapeable.

Mitigation:

- require explicit timeline markers
- keep policy tests for negative cases
- preserve behavior-first regressions

### Under-structured output

If the artifact remains only prose, report/case integration will later require fragile parsing.

Mitigation:

- define the minimal internal field structure now
- keep the external Markdown regular and repetitive

### Premature implementation scope

Timeline extraction already has its own design track. Pulling too much of it into this phase would make the task sprawl.

Mitigation:

- keep this phase focused on artifact boundary, shape, and policy behavior
- defer extraction/ranking improvements to follow-up work

## Success Criteria

- `timeline_artifact` is a clearly defined incident artifact rather than a placeholder kind
- the first version only includes explicitly timestamped events
- the artifact is both human-readable and minimally structured
- policy tests can distinguish stable timeline artifacts from troubleshooting replies
- evidence-first shaping leaves timeline artifacts unchanged
