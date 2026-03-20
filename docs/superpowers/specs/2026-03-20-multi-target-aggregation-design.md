# Multi-Target Aggregation Design

**Date:** 2026-03-20
**Status:** Draft for review
**Owner:** Codex

## Goal

Strengthen HCIGuard's multi-target troubleshooting output so it becomes a stable evidence aggregation layer, not only a fan-out plus text concatenation path.

The first phase should:

- cover `search_log`, `read_log_tail`, `service_status`, and `process_snapshot`
- produce a stable internal aggregation structure
- render human-readable Markdown from that structure
- preserve enough per-target evidence for later timeline and root-cause work

## Problem

HCIGuard already has the foundations for bounded multi-target troubleshooting:

- target definitions, groups, and labels
- confirmation-gated multi-target scope expansion
- controlled fan-out for a small set of readonly tools
- a compact text summary for the current turn

That is enough to make multi-target troubleshooting usable, but not yet strong enough to become a core differentiating capability.

Today the main limitation is not target expansion itself, but result organization:

- the current output is still centered on rendered text
- common findings and per-target differences are derived inline, not represented as stable data
- later capabilities such as cross-target timeline and root-cause candidate mapping would need to re-parse Markdown-like text
- tool-specific grouping behavior is present, but not exposed as a general aggregation contract

This creates a ceiling: HCIGuard can check multiple nodes, but it does not yet have a stable evidence model for multi-target troubleshooting.

## Design Goals

- Keep the current confirmation-gated multi-target troubleshooting flow
- Add one stable aggregation contract above the existing fan-out execution path
- Make shared findings, local findings, failed targets, and raw per-target results explicitly available
- Keep the first version tool-bounded and conservative
- Make rendered output easier for operators to judge quickly
- Avoid forcing later timeline/candidate work to parse presentation text

## Non-Goals

- No redesign of target resolution or confirmation gating
- No expansion to new multi-target tools beyond the first four in this phase
- No cross-target incident timeline in this phase
- No automatic root-cause scoring in this phase
- No full cluster orchestration framework
- No UI-specific redesign

## Scope

This phase covers only these multi-target troubleshooting tools:

- `search_log`
- `read_log_tail`
- `service_status`
- `process_snapshot`

These tools are enough to exercise two main aggregation modes:

- log-oriented evidence comparison
- service/process state comparison

## Design Summary

Introduce a stable aggregation object for multi-target troubleshooting results.

Execution remains the same at a high level:

1. one supported tool call is expanded across confirmed targets
2. raw per-target results are collected
3. a tool-aware aggregator converts them into a stable internal structure
4. a formatter renders that structure into the user-visible Markdown summary

The key change is that step 3 becomes explicit and reusable.

## Internal Aggregation Contract

The first stable contract should represent both the raw per-target observations and the normalized grouped findings.

Recommended top-level fields:

- `tool_name`
- `targets_total`
- `ok_targets`
- `failed_targets`
- `shared_findings`
- `local_findings`
- `per_target_results`

### Top-Level Field Intent

- `tool_name`: the multi-target tool being aggregated
- `targets_total`: total number of resolved targets for the invocation
- `ok_targets`: ordered list of successful target IDs
- `failed_targets`: ordered list of failed target entries with reasons
- `shared_findings`: normalized findings observed on two or more targets
- `local_findings`: normalized findings observed on exactly one target
- `per_target_results`: original ordered target results preserved for later reuse

## Failed Target Structure

Each failed target entry should include:

- `target_id`
- `target_host`
- `status`
- `error`

Version 1 only needs to distinguish failure at the per-target level. It does not need a larger failure taxonomy yet.

## Finding Structure

Each aggregated finding should include:

- `signature`
- `target_ids`
- `target_hosts`
- `count`
- `kind`
- `sample_evidence`

Recommended field intent:

- `signature`: normalized finding identity used for grouping
- `target_ids`: ordered targets carrying the finding
- `target_hosts`: ordered hosts carrying the finding
- `count`: number of targets in the group
- `kind`: lightweight category such as `shared` or `local`
- `sample_evidence`: one concise evidence snippet preserved for operator reading

Version 1 does not need a rich ontology of finding kinds. A small stable set is enough.

## Per-Target Result Structure

Each raw per-target result should include:

- `target_id`
- `target_host`
- `status`
- `content`
- `error`
- `observed_at`

This mostly matches the current collection shape and should remain close to the execution path.

The main rule is:

- aggregated findings are summaries
- per-target results remain the source-preserving layer

Later work such as timeline extraction or candidate mapping should be able to start from `per_target_results` without scraping formatted summary text.

## Tool-Aware Aggregation Rules

Version 1 should stay conservative and continue using tool-aware normalization.

### Log Tools

For `search_log` and `read_log_tail`:

- strip target-specific wrappers and obvious log headers
- normalize timestamps or line-number prefixes only where current logic already does so safely
- group comparable evidence into shared or local findings
- preserve one concise evidence example per grouped finding

The goal is not to build a full log correlation engine. The goal is to make repeated patterns across targets visible and reusable.

### State Tools

For `service_status` and `process_snapshot`:

- normalize target-specific prefixes
- group identical or near-identical state summaries
- keep local-only states visible when only one target differs

The output should let an operator quickly answer:

- all nodes look the same
- one node differs
- some nodes failed to return data

## Rendering Rules

The user-visible output should still be Markdown, but it should be rendered from the stable aggregation object.

Recommended layout:

```md
## Multi-Target Summary: service_status

Targets: 3 total, 2 ok, 1 failed

### Shared Findings
- node-a, node-b: kubelet active (running)

### Local Findings
- node-c: kubelet inactive (dead)

### Failed Targets
- node-d: ssh timeout

## Per-Target Results

[multi-target][node-a -> root@10.0.0.1]
...
```

Rendering rules:

- keep the top summary compact and operator-readable
- always separate shared, local, and failed sections when present
- preserve per-target raw results below the grouped summary
- do not force empty sections to render

## Relationship To Existing Code

This design should build on the current `nanobot/agent/multi_target.py` path rather than replace it.

Expected evolution:

- current collection of raw per-target results remains
- current signature normalization becomes part of an explicit aggregator layer
- Markdown rendering moves to a formatter driven by the aggregation object

This keeps the current behavior recognizable while giving the code a stable structure for later phases.

## Testing Goals

The first implementation phase should prove both structure and rendering.

Tests should cover:

- aggregation of shared findings across multiple successful targets
- separation of local findings when exactly one target differs
- failed targets staying outside grouped findings
- stable ordering of grouped findings and targets
- formatter output for each supported tool family
- preservation of per-target raw results for later reuse

The tests should remain bounded to the four supported tools in this phase.

## Acceptance Criteria

This design is successful when:

- multi-target aggregation produces a stable internal structure for the first four tools
- user-visible output becomes easier to judge quickly
- later phases can reuse aggregation data without re-parsing Markdown
- the current confirmation-gated troubleshooting flow remains unchanged

## Why This Phase Comes First

This phase should come before cross-target timeline and candidate work because it creates the evidence contract those later features need.

Without a stable aggregation layer:

- timeline work must parse presentation text
- candidate work must infer from loosely rendered summaries
- each later feature risks inventing its own incompatible grouping logic

With this layer in place, later multi-target analysis can build on one shared model.
