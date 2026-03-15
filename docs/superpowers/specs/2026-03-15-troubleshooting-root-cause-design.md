# Troubleshooting Root Cause Advisor (Log Evidence Driven) - Design

## Context
The goal is a general-purpose troubleshooting agent that can suggest likely root causes and
concrete, verifiable fix steps, but never executes changes. Output must cite log evidence.

Primary data sources are application logs and blackbox logs under `/sf/log`.

## Goals
- General-purpose troubleshooting across services using logs as evidence.
- Output is structured: symptom, root cause judgement, evidence citations, fix steps, risk/rollback.
- High-confidence suggestions require >= 2 evidence lines with timestamps.
- If evidence is insufficient or no rule matches, return "needs manual intervention".

## Non-Goals
- No auto-remediation or write actions.
- No multi-host orchestration in this phase.
- No hard-coded timestamp parsing logic in code (patterns are configurable).

## Scope and Assumptions
- Log sources:
  - App logs: `/sf/log/<date>/*.log`
  - Blackbox logs: `/sf/log/blackbox/<date>/*.log`
  - VN blackbox logs: `/sf/log/vn-blackbox/<date>/*.log`
- `<date>` can be `today`, `YYYYMMDD`, `YYYY-MM-DD`, or single day like `15`.
- If user does not specify time range, the agent must ask.
- If user does not specify service or keywords, do candidate discovery first.

## Workflow
1. **Parameter completion**
   - Ask for time range if missing.
   - If service/keywords are missing, run discovery.
2. **Candidate discovery**
   - Use user keywords + generic keywords (error/fail/timeout/exception/panic/oom).
   - Recursive scan under the log roots for candidate files.
3. **Evidence extraction**
   - Scan candidate files efficiently and extract lines that match evidence patterns.
   - Extract timestamp fragments using configurable regex patterns (no hard-coded parsing).
4. **Rule matching**
   - Match evidence patterns against YAML rules.
   - Require >= 2 evidence lines with timestamps before "high confidence".
5. **Output**
   - Structured response with mandatory evidence citations.
   - If insufficient evidence: "needs manual intervention" + missing info.

## Evidence Model
Each evidence item must include:
- File path
- Timestamp fragment (extracted by pattern)
- Line content

Evidence lines are grouped by rule and by source file. Output should include at least two
distinct evidence lines (can be same file).

## Rule Library (YAML)
Store under `nanobot/knowledge/root_cause/` as YAML files, versioned in repo.

Suggested schema:
```yaml
id: upgrade_worker_stuck
title: Upgrade worker stuck on precheck
sources:
  - /sf/log/<date>/upgrade-worker.log
evidence_patterns:
  - "precheck failed"
  - "exit code: 2"
timestamp_patterns:
  - "^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}"
min_evidence: 2
root_cause: "Upgrade worker precheck failed"
fix_steps:
  - "Verify dependency service is reachable"
  - "Retry upgrade after confirming precheck inputs"
rollback: "If retry fails, revert to previous release and re-run precheck"
confidence: "high"
```

Notes:
- `timestamp_patterns` are per-rule and optional defaults can be used.
- `sources` should include `<date>` token expanded at runtime.
- Rules without sufficient evidence must not produce high-confidence output.

## Confidence and Output Policy
- High confidence: rule matched + >= 2 evidence lines with timestamps.
- Medium/low confidence: rule matched but evidence < 2 or partial patterns.
- If no rule match or timestamp extraction fails: "needs manual intervention".

Output template (required fields):
1. Symptom
2. Root cause judgement (with confidence)
3. Evidence citations (path + timestamp + line)
4. Fix steps (verifiable, no execution)
5. Risk / rollback

## Performance and Safety
- Use efficient scanning (e.g., ripgrep or streaming read).
- No hard scan limit, but avoid loading full files into memory.
- Read-only operations only.

## Open Questions
- Default generic keyword list to ship with v1.
- Whether to deduplicate evidence across files by normalized message.
- Policy for "date" expansion when multiple date directories exist.
