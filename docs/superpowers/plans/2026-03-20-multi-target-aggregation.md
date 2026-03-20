# Multi-Target Aggregation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stable multi-target aggregation contract and formatter for `search_log`, `read_log_tail`, `service_status`, and `process_snapshot` so HCIGuard can compare shared/local/failed evidence instead of only concatenating per-target results.

**Architecture:** Keep the current confirmation-gated multi-target troubleshooting flow and raw per-target collection in `nanobot/agent/multi_target.py`, but insert an explicit aggregation layer between collection and rendering. The first phase should add stable internal aggregation data, keep raw per-target evidence intact, and render Markdown from the structured aggregation object rather than from inline string assembly.

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio

---

## File Structure

- Modify: `nanobot/agent/multi_target.py`
  Responsibility: add the aggregation contract, tool-aware aggregation helpers, and formatter integration while preserving the existing fan-out path.
- Modify: `tests/test_multi_target_troubleshooting.py`
  Responsibility: add focused aggregation and rendering tests for the four supported tools.
- Modify: `docs/superpowers/plans/2026-03-20-multi-target-aggregation.md`
  Responsibility: reflect actual execution status.

## Chunk 1: Lock The Aggregation Contract

### Task 1: Add focused failing tests for the stable aggregation structure

**Files:**
- Modify: `tests/test_multi_target_troubleshooting.py`

- [x] **Step 1: Write failing tests for log-oriented aggregation**

Add focused tests for `search_log` / `read_log_tail` style results proving:

- two successful targets with the same normalized signature land in `shared_findings`
- one differing successful target lands in `local_findings`
- failed targets stay in `failed_targets` and do not appear in grouped findings
- `per_target_results` preserves ordered raw target entries
- grouped findings expose the expected stable fields: `signature`, `target_ids`, `target_hosts`, `count`, `kind`, `sample_evidence`
- failed target entries expose the expected stable fields: `target_id`, `target_host`, `status`, `error`

Use representative raw collected result dicts shaped like the current `execute_multi_target_tool(...)` path.

- [x] **Step 2: Write failing tests for state-oriented aggregation**

Add focused tests for `service_status` / `process_snapshot` style results proving:

- identical normalized state summaries group into one shared finding
- one target with a different state becomes a local finding
- target ordering in `target_ids` remains stable and deterministic
- each `per_target_results` entry preserves the expected stable fields: `target_id`, `target_host`, `status`, `content`, `error`, `observed_at`

- [x] **Step 3: Run the focused aggregation tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_multi_target_troubleshooting.py -k "aggregation or shared_findings or local_findings or failed_targets" -v
```

Expected: FAIL because the stable aggregation contract does not exist yet.

- [x] **Step 4: Commit the red test slice if it is isolated and readable**

```bash
git add tests/test_multi_target_troubleshooting.py
git commit -m "test: add multi-target aggregation coverage"
```

If you do not want a red commit on the branch, skip the commit and proceed directly to Task 2.

### Task 2: Implement the stable aggregation contract and make the tests green

**Files:**
- Modify: `nanobot/agent/multi_target.py`
- Modify: `tests/test_multi_target_troubleshooting.py`

- [x] **Step 1: Add the minimal stable aggregation structure**

Implement the smallest internal structure needed to represent:

- `tool_name`
- `targets_total`
- `ok_targets`
- `failed_targets`
- `shared_findings`
- `local_findings`
- `per_target_results`

Keep the first version local to `nanobot/agent/multi_target.py`. If dataclasses help, keep them focused and private to this module.

- [x] **Step 2: Lock the stable nested field shapes**

Implement the smallest nested structures needed so the tests can rely on stable fields for:

- `failed_targets`
- `shared_findings`
- `local_findings`
- `per_target_results`

Do not add extra taxonomy or optional fields beyond the approved spec.

- [x] **Step 3: Add tool-aware aggregation helpers**

Implement minimal helpers that:

- separate successful and failed targets
- normalize signatures with the existing tool-aware rules
- group findings into `shared_findings` and `local_findings`
- preserve deterministic ordering of targets and grouped findings

Do not broaden the supported tool set in this phase.

- [x] **Step 4: Run the focused aggregation tests**

Run:

```bash
python3 -m pytest tests/test_multi_target_troubleshooting.py -k "aggregation or shared_findings or local_findings or failed_targets" -v
```

Expected: PASS

- [x] **Step 5: Run a broader multi-target troubleshooting slice**

Run:

```bash
python3 -m pytest tests/test_multi_target_troubleshooting.py -v
```

Expected: PASS

- [x] **Step 6: Commit**

```bash
git add nanobot/agent/multi_target.py tests/test_multi_target_troubleshooting.py
git commit -m "feat: add stable multi-target aggregation structure"
```

## Chunk 2: Render Markdown From Structured Aggregation

### Task 3: Add failing formatter tests for stable Markdown rendering

**Files:**
- Modify: `tests/test_multi_target_troubleshooting.py`

- [x] **Step 1: Write failing formatter tests for grouped summary rendering**

Add focused tests proving the rendered summary:

- starts with `## Multi-Target Summary: <tool_name>`
- shows compact target counts
- renders `### Shared Findings`, `### Local Findings`, and `### Failed Targets` only when present
- preserves raw per-target results under `## Per-Target Results`

- [x] **Step 2: Write failing formatter tests for both supported tool families**

Add focused tests proving rendering remains stable for:

- one log-oriented tool (`search_log` or `read_log_tail`)
- one state-oriented tool (`service_status` or `process_snapshot`)

The tests should confirm that both tool families render grouped findings from the same stable aggregation contract, without falling back to tool-specific inline string assembly.

- [x] **Step 3: Write failing formatter tests for empty-section omission**

Add focused tests proving:

- no `Shared Findings` section is rendered when no shared findings exist
- no `Local Findings` section is rendered when no local findings exist
- no `Failed Targets` section is rendered when all targets succeed

- [x] **Step 4: Run the focused formatter tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_multi_target_troubleshooting.py -k "formatter or render or summary" -v
```

Expected: FAIL because rendering is still assembled inline from collected text.

### Task 4: Implement stable rendering and keep the fan-out behavior intact

**Files:**
- Modify: `nanobot/agent/multi_target.py`
- Modify: `tests/test_multi_target_troubleshooting.py`

- [x] **Step 1: Add a formatter for the stable aggregation structure**

Implement a formatter that renders the grouped summary from the aggregation object and appends the raw per-target results after it.

Keep rendering rules conservative:

- compact operator-readable summary first
- grouped findings in dedicated sections
- raw per-target results preserved below
- no forced empty sections

- [x] **Step 2: Keep formatter coverage stable across log and state tool families**

Ensure the formatter path handles both:

- log-oriented grouped findings
- state-oriented grouped findings

without introducing separate incompatible rendering contracts.

- [x] **Step 3: Route `execute_multi_target_tool(...)` through aggregation then formatting**

Update `execute_multi_target_tool(...)` so it:

- still collects the same raw per-target results
- builds the aggregation object
- formats the user-visible Markdown from that object

Do not change confirmation gating or target resolution behavior.

- [x] **Step 4: Run the focused formatter tests**

Run:

```bash
python3 -m pytest tests/test_multi_target_troubleshooting.py -k "formatter or render or summary" -v
```

Expected: PASS

- [x] **Step 5: Run the full multi-target troubleshooting test file**

Run:

```bash
python3 -m pytest tests/test_multi_target_troubleshooting.py -v
```

Expected: PASS

- [x] **Step 6: Commit**

```bash
git add nanobot/agent/multi_target.py tests/test_multi_target_troubleshooting.py
git commit -m "feat: render multi-target summaries from aggregation"
```

## Chunk 3: Verify Behavior Preservation And Sync Plan

### Task 5: Run final regressions and sync the plan

**Files:**
- Modify: `docs/superpowers/plans/2026-03-20-multi-target-aggregation.md`

- [x] **Step 1: Run focused multi-target and troubleshooting regressions**

Run:

```bash
python3 -m pytest tests/test_multi_target_troubleshooting.py tests/test_agentloop_troubleshooting_flow.py -k "multi_target or target_expansion or target_confirmation or aggregation or summary" -v
```

Expected: PASS

- [x] **Step 2: Run the full multi-target and workflow slices**

Run:

```bash
python3 -m pytest tests/test_multi_target_troubleshooting.py tests/test_agentloop_troubleshooting_flow.py tests/test_target_resolver.py -v
```

Expected: PASS

- [x] **Step 3: Optionally run the full suite if no unrelated failures are known**

Run:

```bash
python3 -m pytest -q
```

Expected: PASS, or document any unrelated pre-existing failure clearly.

- [x] **Step 4: Mark completed plan checkboxes**

Update this plan to reflect actual execution status.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-03-20-multi-target-aggregation.md
git commit -m "docs: sync multi-target aggregation plan status"
```
