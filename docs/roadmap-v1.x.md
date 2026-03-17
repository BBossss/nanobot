# HCIGuard Roadmap (V1.x)

This document defines the practical evolution path from today's stable V1 baseline to a stronger V1.x troubleshooting product.

## North Star

Turn HCIGuard from a single-node troubleshooting assistant into a multi-target, evidence-driven incident copilot while keeping safety and auditability first.

## Baseline (Current V1)

- HCI-focused troubleshooting flow with investigation-first tools.
- Readonly-by-default execution model with approval controls.
- Case recording, inspection reports, and unified command audit.
- CLI + Telegram + Mattermost operational entrypoints.

## V1.1 (Near-Term): Multi-Target Foundations

Goal: move from single-node strength to controlled multi-target operations.

- Add host tagging and target grouping for inspection/troubleshooting.
- Support batched inspection targeting with consistent result schema.
- Keep per-target execution and audit boundaries explicit.

Exit criteria:

- One command/request can run the same inspection profile on multiple targets.
- Reports and case evidence are grouped by target and time window.
- Audit logs can trace each action to an exact target identity.

### V1.1 Execution Breakdown

Use this as the implementation checklist for planning and delivery.

| Module | Task | Acceptance criteria |
| --- | --- | --- |
| Config model | Add multi-target schema for grouping/tagging (`targets`, `groups`, `labels`) | Invalid config fails fast with clear validation errors; valid config supports at least 3 targets in one group |
| Target resolver | Resolve explicit target list from group/tag filters | Given a group/tag input, resolved target set is deterministic and stable across runs |
| Inspection runner | Execute one inspection profile across resolved targets | One command triggers N-target execution and returns per-target status (`ok`/`failed`/`skipped`) |
| Troubleshooting tools | Pass target identity through tool context and outputs | Tool output always includes `target_id` and `target_host` when target is remote |
| Report pipeline | Group evidence by target + time window in report output | Generated report has per-target sections and shared summary section |
| Case integration | Write multi-target evidence links into case records | Case file references all target-specific artifacts for the same incident window |
| Audit pipeline | Ensure every executed action records target metadata | Each audit entry contains `target`, `executor`, `command`, `timestamp`, `result` |
| Channel UX (CLI/IM) | Show explicit target scope in prompts and summaries | User can see "which targets were included" before and after execution |
| Regression tests | Add focused tests for multi-target config/resolve/run/report/audit | CI includes dedicated V1.1 regression files and all pass on default pipeline |

### V1.1 Suggested Delivery Order

1. `Config model` + `Target resolver`
2. `Inspection runner` + `Troubleshooting tools`
3. `Report pipeline` + `Case integration` + `Audit pipeline`
4. `Channel UX`
5. `Regression tests` + release checklist

### V1.1 Definition of Done

- Multi-target inspection is usable from one command/request.
- Evidence is traceable per target in reports, cases, and audits.
- Error handling clearly distinguishes per-target partial failure vs full-run failure.
- CI covers the multi-target critical path with deterministic regression tests.

V1.1 execution template:

- [V1.1 issue template](v1.1-issue-template.md)
- [V1.1 implementation plan (superpowers)](superpowers/plans/2026-03-18-v1-1-multi-target-foundations.md)

## V1.2: Cross-Target Correlation

Goal: connect evidence across hosts and services.

- Add time-window correlation for logs, service state, and events.
- Build a minimal incident timeline view in report output.
- Highlight likely shared root-cause candidates across targets.

Exit criteria:

- A single incident report can explain "what happened first" across multiple targets.
- Correlation output includes evidence links, not only summary text.

## V1.3: Case Lifecycle and Handoff

Goal: make the output operationally reusable across team shifts.

- Add case status flow (`new`, `triaging`, `mitigating`, `monitoring`, `resolved`).
- Support evidence linking between inspection runs and case updates.
- Add handoff-ready summaries for IM-driven operations.

Exit criteria:

- Teams can continue the same case without redoing the investigation context.
- Case history records who did what, when, and on which targets.

## V1.4: Reliability and Scale Hardening

Goal: improve confidence under production pressure.

- Expand focused regression set for multi-target and correlation paths.
- Add CI quality gates for critical troubleshooting workflows.
- Improve failure taxonomy in reports (`unknown`, `partial`, `blocked`, `confirmed`).

Exit criteria:

- Critical workflows have deterministic regression coverage in CI.
- Failures are classified with clear operator-facing next actions.

## Non-Goals in V1.x

- Unrestricted automatic remediation execution.
- Full autonomous multi-agent orchestration.
- Heavy production web console inside this repository.

## Tracking

Suggested release tracking format:

- Version goal
- Scope in/out
- Exit criteria
- Demo scenario
- Regression checklist
