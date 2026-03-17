# Root Cause Candidates Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add evidence-driven candidate root cause generation that derives a small set of programmatic candidate types from the current multi-target summary, timeline, and log evidence, then renders them as constrained “候选根因” output.

**Architecture:** Keep collection and timeline generation unchanged, then add a post-processing layer that extracts bounded signals from the current evidence, maps them to a fixed candidate type set, and renders only supported candidate types with supporting evidence. Do not use historical cases, external rule files, or unconstrained LLM generation in this phase.

**Tech Stack:** Python 3.11+, `re`, dataclasses, pytest, pytest-asyncio

---

## Chunk 1: Signal Extraction And Candidate Mapping

### Task 1: Add root-cause candidate module and bounded signal extraction

**Files:**
- Create: `nanobot/agent/root_cause_candidates.py`
- Test: `tests/test_root_cause_candidates.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove the module can extract stable signals from current evidence text.

Cover:
- timeout / unreachable style signals
- retry / exceeded style signals
- service exit / crash style signals
- cross-node-common vs single-node-only hints

Example skeleton:

```python
def test_extract_signals_detects_timeout_and_cross_node_common() -> None:
    result = extract_candidate_signals(...)
    assert "timeout" in result.signals
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_root_cause_candidates.py -k "extract_signals" -v`
Expected: FAIL because `nanobot.agent.root_cause_candidates` does not exist

- [ ] **Step 3: Implement minimal signal extraction**

Create:
- a lightweight candidate structure
- `extract_candidate_signals(...)`
- simple keyword/pattern matching over:
  - multi-target summary
  - timeline summary
  - raw evidence snippets

Keep signal vocabulary fixed and small.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_root_cause_candidates.py -k "extract_signals" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/root_cause_candidates.py tests/test_root_cause_candidates.py
git commit -m "feat: add root cause signal extraction"
```

### Task 2: Map extracted signals to a fixed candidate type set

**Files:**
- Modify: `nanobot/agent/root_cause_candidates.py`
- Test: `tests/test_root_cause_candidates.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove:
- timeout + cross-node-common => `跨节点共享连接/超时异常`
- single-node-only => `局部节点异常`
- retry-exhausted => `重试耗尽/任务卡住`
- service-exit/crash => `服务执行失败/异常退出`
- dependency/backend hints => `依赖不可达或下游异常`
- weak/insufficient evidence => no candidates

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_root_cause_candidates.py -k "map_candidates or insufficient" -v`
Expected: FAIL because candidate mapping is missing or incomplete

- [ ] **Step 3: Implement minimal candidate mapping**

Add:
- a fixed candidate type enum or constants
- deterministic mapping rules from signals to candidate types
- guardrails that require more than one weak hint before emitting a candidate

Limit final candidates to at most 2 items.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_root_cause_candidates.py -k "map_candidates or insufficient" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/root_cause_candidates.py tests/test_root_cause_candidates.py
git commit -m "feat: map evidence signals to root cause candidates"
```

## Chunk 2: Render Constrained Candidate Output

### Task 3: Render candidate root cause output with supporting evidence

**Files:**
- Modify: `nanobot/agent/root_cause_candidates.py`
- Test: `tests/test_root_cause_candidates.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove:
- output contains `Candidate Root Cause`
- output contains `Supporting Evidence`
- each emitted candidate has 2-4 supporting evidence lines
- output does not contain “已确认根因”
- output never contains unknown candidate types

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_root_cause_candidates.py -k "render or supporting" -v`
Expected: FAIL because constrained rendering is missing

- [ ] **Step 3: Implement minimal renderer**

Implement:
- `render_candidate_root_causes(...)`
- fixed two-section output
- evidence clipping so output stays concise

If there are no candidates, render a short “当前证据不足以形成候选根因” message instead.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_root_cause_candidates.py -k "render or supporting" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/root_cause_candidates.py tests/test_root_cause_candidates.py
git commit -m "feat: render constrained root cause candidates"
```

## Chunk 3: Integrate With Current Multi-Target Analysis

### Task 4: Append candidate root cause output to current multi-target summaries

**Files:**
- Modify: `nanobot/agent/multi_target.py`
- Test: `tests/test_multi_target_troubleshooting.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove:
- when evidence supports a candidate, multi-target summary includes `Candidate Root Cause`
- when evidence is insufficient, no fake candidate section is added
- timeline/log evidence can contribute to candidate generation

Example skeleton:

```python
def test_aggregate_multi_target_results_includes_candidate_root_cause() -> None:
    summary = aggregate_multi_target_results(...)
    assert "Candidate Root Cause" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_multi_target_troubleshooting.py -k "candidate_root_cause" -v`
Expected: FAIL because multi-target summary does not integrate candidate output

- [ ] **Step 3: Integrate candidate generation**

Update `aggregate_multi_target_results(...)` so that:
- it builds signal input from current summary/timeline/raw evidence
- appends candidate root cause output only when candidates are present
- preserves current sections (`Common Findings`, `Local Findings`, `Failed Targets`, `Timeline`)

Do not add LLM calls in this task. Keep it fully programmatic.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_multi_target_troubleshooting.py -k "candidate_root_cause" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/multi_target.py tests/test_multi_target_troubleshooting.py
git commit -m "feat: append candidate root causes to multi-target summary"
```

## Chunk 4: Edge Cases And Regression Guards

### Task 5: Add guards for weak evidence and conflicting candidates

**Files:**
- Modify: `nanobot/agent/root_cause_candidates.py`
- Test: `tests/test_root_cause_candidates.py`
- Test: `tests/test_multi_target_troubleshooting.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- single weak hint does not emit a candidate
- more than two possible candidates are clipped to two
- conflicting evidence does not produce “confirmed” wording

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_root_cause_candidates.py tests/test_multi_target_troubleshooting.py -k "weak or conflicting or clip" -v`
Expected: FAIL because guardrails are incomplete

- [ ] **Step 3: Implement guardrails**

Add:
- minimum evidence thresholds
- candidate count cap
- wording protections to keep everything explicitly “候选”

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_root_cause_candidates.py tests/test_multi_target_troubleshooting.py -k "weak or conflicting or clip" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/root_cause_candidates.py tests/test_root_cause_candidates.py tests/test_multi_target_troubleshooting.py
git commit -m "test: guard root cause candidate output"
```

## Chunk 5: Final Verification

### Task 6: Run focused and adjacent regressions

**Files:**
- Test: `tests/test_root_cause_candidates.py`
- Test: `tests/test_multi_target_troubleshooting.py`
- Test: `tests/test_log_timeline.py`

- [ ] **Step 1: Run focused candidate tests**

Run:

```bash
python3 -m pytest \
  tests/test_root_cause_candidates.py \
  tests/test_multi_target_troubleshooting.py -v
```

Expected:
- root-cause candidate tests PASS
- multi-target summary still PASS with timeline and candidate sections together

- [ ] **Step 2: Run adjacent regressions**

Run:

```bash
python3 -m pytest \
  tests/test_log_timeline.py \
  tests/test_agentloop_troubleshooting_flow.py \
  tests/test_troubleshooting_tools.py -v
```

Expected:
- timeline output still PASS
- confirmation-gated multi-target flow still PASS
- tool outputs remain unchanged

- [ ] **Step 3: Review diff for scope control**

Run:

```bash
git diff --stat
git diff -- nanobot/agent/root_cause_candidates.py nanobot/agent/multi_target.py tests/test_root_cause_candidates.py tests/test_multi_target_troubleshooting.py
```

Expected:
- candidate logic remains concentrated in the planned files
- no accidental coupling to cases or external rule systems

- [ ] **Step 4: Commit final integration**

```bash
git add nanobot/agent/root_cause_candidates.py nanobot/agent/multi_target.py tests/test_root_cause_candidates.py tests/test_multi_target_troubleshooting.py docs/superpowers/specs/2026-03-18-root-cause-candidates-design.md docs/superpowers/plans/2026-03-18-root-cause-candidates.md
git commit -m "feat: add evidence-driven root cause candidates"
```
