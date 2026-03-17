# CLI First 安装与首日体验 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the local CLI install and first-run experience easy enough that an engineer can install with `uv tool install nanobot-ai`, run `nanobot`, complete a minimal onboarding flow, verify readiness with `doctor`, and then see strong progress feedback during the first troubleshooting run.

**Architecture:** Keep the existing CLI structure and command surface, then add a lightweight bootstrap gate at the `nanobot` entrypoint that only intercepts when minimal configuration is missing. Build the experience around four bounded components: onboarding wizard, doctor, quickstart, and progress feedback, while keeping advanced provider/channel setup out of the first-run path.

**Tech Stack:** Python 3.11+, Typer, prompt-toolkit, Pydantic settings/schema, pytest, pytest-asyncio

---

## Chunk 1: CLI Bootstrap And Minimal Onboarding

### Task 1: Map current CLI entrypoints and first-run behavior

**Files:**
- Modify: `docs/superpowers/plans/2026-03-18-cli-first-install-experience.md`
- Inspect: `nanobot/cli/commands.py`
- Inspect: `nanobot/config/loader.py`
- Inspect: `nanobot/utils/helpers.py`
- Inspect: `tests/test_commands.py`
- Inspect: `tests/test_cli_input.py`

- [ ] **Step 1: Inspect current CLI bootstrap path**

Read the existing `nanobot` command entrypoints and determine:
- which command currently runs when the bare CLI is invoked
- how config paths are resolved
- how workspace paths are created
- whether prompt-toolkit helpers already exist for interactive input

- [ ] **Step 2: Record exact implementation boundaries in this plan**

Update the file list in this plan if the actual codebase uses different modules than expected. Keep the implementation focused in the current CLI layer instead of introducing a new bootstrap framework.

- [ ] **Step 3: No code changes in this task**

Do not implement anything yet. This task exists so later workers do not guess file boundaries.

### Task 2: Add failing tests for automatic first-run onboarding

**Files:**
- Modify: `tests/test_commands.py`
- Modify: `tests/test_cli_input.py`
- Inspect: `nanobot/cli/commands.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove:
- invoking bare `nanobot` with missing minimal config enters onboarding instead of failing immediately
- invoking bare `nanobot` with valid minimal config does not enter onboarding
- cancelling onboarding does not write partial config

Example skeleton:

```python
def test_root_command_runs_onboarding_when_minimal_config_missing(...) -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "onboarding" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_commands.py tests/test_cli_input.py -k "onboarding or root_command" -v`
Expected: FAIL because the bare CLI does not yet auto-bootstrap into onboarding

- [ ] **Step 3: Implement minimal CLI bootstrap gate**

Update `nanobot/cli/commands.py` so that:
- the bare `nanobot` entrypoint checks whether minimal config exists
- missing minimal config triggers the onboarding flow
- existing valid config preserves current behavior
- interrupted onboarding does not persist partial config

Prefer a small helper such as `_needs_minimal_bootstrap(...)` rather than spreading checks across many commands.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_commands.py tests/test_cli_input.py -k "onboarding or root_command" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_commands.py tests/test_cli_input.py nanobot/cli/commands.py
git commit -m "feat: bootstrap cli into onboarding on first run"
```

### Task 3: Convert onboarding into a minimal OpenAI-compatible wizard

**Files:**
- Modify: `nanobot/cli/commands.py`
- Modify: `nanobot/config/schema.py`
- Modify: `tests/test_commands.py`
- Modify: `tests/test_cli_input.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove onboarding:
- asks only for `base_url`, `api_key`, and `model` on the default path
- writes minimal config fields:
  - `agents.defaults.provider`
  - `agents.defaults.model`
  - `providers.openai.base_url`
  - `providers.openai.api_key`
- initializes the workspace when it does not exist

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_commands.py tests/test_cli_input.py -k "minimal_config or workspace_init or openai_compatible" -v`
Expected: FAIL because the current onboarding path writes different or incomplete fields

- [ ] **Step 3: Implement the minimal wizard**

Update onboarding so that:
- the default path is `OpenAI-compatible`
- only the three required fields are prompted on the default path
- advanced provider/channel setup remains out of the first-run flow
- workspace/bootstrap templates are created as part of onboarding

Keep schema changes minimal; do not redesign the full config tree in this task.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_commands.py tests/test_cli_input.py -k "minimal_config or workspace_init or openai_compatible" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/cli/commands.py nanobot/config/schema.py tests/test_commands.py tests/test_cli_input.py
git commit -m "feat: add minimal openai-compatible onboarding"
```

## Chunk 2: Doctor And Quickstart

### Task 4: Add a doctor command with bounded readiness checks

**Files:**
- Modify: `nanobot/cli/commands.py`
- Create or Modify: `nanobot/cli/doctor.py`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove `nanobot doctor` reports structured status for:
- missing config
- missing workspace
- incomplete provider fields
- reachable vs unreachable default model path

Output should clearly expose `ok`, `partial`, or `blocked`.

Example skeleton:

```python
def test_doctor_reports_blocked_when_provider_config_missing(...) -> None:
    result = runner.invoke(app, ["doctor"])
    assert "blocked" in result.output
    assert "api_key" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_commands.py -k "doctor" -v`
Expected: FAIL because `doctor` is missing or not structured as required

- [ ] **Step 3: Implement doctor**

Add a bounded readiness check command that:
- does not mutate user config
- verifies config file presence
- verifies workspace presence
- verifies minimum provider/model fields
- attempts a lightweight connectivity/model readiness check where feasible

If a live provider check would make tests flaky, isolate it behind a helper that can be mocked in tests.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_commands.py -k "doctor" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/cli/commands.py nanobot/cli/doctor.py tests/test_commands.py
git commit -m "feat: add cli doctor command"
```

### Task 5: Add a quickstart command for the shortest usable path

**Files:**
- Modify: `nanobot/cli/commands.py`
- Modify: `tests/test_commands.py`
- Modify: `README.md`
- Modify: `README.zh-CN.md`

- [ ] **Step 1: Write the failing tests**

Add tests that prove `nanobot quickstart` includes:
- `uv tool install nanobot-ai`
- `nanobot`
- `nanobot doctor`
- `nanobot agent`

The command should be informational only and should not write config.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_commands.py -k "quickstart" -v`
Expected: FAIL because `quickstart` does not exist or lacks the required output

- [ ] **Step 3: Implement quickstart and update docs**

Add `nanobot quickstart` and update both READMEs so the primary local install path is:

```bash
uv tool install nanobot-ai
```

Keep alternative installation methods out of the primary quickstart narrative.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_commands.py -k "quickstart" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/cli/commands.py tests/test_commands.py README.md README.zh-CN.md
git commit -m "docs: add cli quickstart path"
```

## Chunk 3: Strong Progress Feedback During Troubleshooting

### Task 6: Add failing tests for stage-based troubleshooting progress

**Files:**
- Modify: `tests/test_agentloop_investigation.py`
- Modify: `tests/test_agentloop_troubleshooting_flow.py`
- Inspect: `nanobot/agent/loop.py`
- Inspect: `nanobot/bus/events.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove the first troubleshooting run can emit stage-oriented progress such as:
- `初始化上下文`
- `识别目标/范围`
- `生成调查计划`
- `执行只读检查`
- `汇总证据`
- `输出判断`

Also cover multi-target progress if a confirmed multi-target scope exists.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -k "progress or stage" -v`
Expected: FAIL because the current progress output is missing or too weak

- [ ] **Step 3: Implement the progress layer**

Update `nanobot/agent/loop.py` so that:
- progress updates are explicit and human-readable
- long-running investigation steps are no longer silent
- tool execution can expose current tool name
- confirmed multi-target runs can expose per-target progress

Keep the design additive. Do not redesign the whole bus/event model in this task.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -k "progress or stage" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/loop.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: strengthen troubleshooting progress feedback"
```

## Chunk 4: Integration And Guardrails

### Task 7: Verify the first-run flow end to end

**Files:**
- Modify: `tests/test_commands.py`
- Modify: `tests/test_cli_input.py`
- Modify: `tests/test_agentloop_investigation.py`

- [ ] **Step 1: Add focused end-to-end regression tests**

Cover:
- fresh install style state -> bare `nanobot` -> onboarding
- onboarding success -> `doctor` passes key checks
- first troubleshooting run emits progress feedback

Prefer CLI-focused tests with mocks over slow live network calls.

- [ ] **Step 2: Run focused verification**

Run:

```bash
python3 -m pytest \
  tests/test_commands.py \
  tests/test_cli_input.py \
  tests/test_agentloop_investigation.py \
  tests/test_agentloop_troubleshooting_flow.py -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_commands.py tests/test_cli_input.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "test: cover cli first-run experience"
```

### Task 8: Run full verification and update docs references

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/development-status-v1.md`

- [ ] **Step 1: Update product-facing docs**

Ensure the docs consistently reflect:
- the official install command
- first-run onboarding behavior
- `doctor`
- `quickstart`

- [ ] **Step 2: Run repository verification**

Run:

```bash
python3 -m pytest
```

Expected: PASS

Run:

```bash
ruff check nanobot/cli/commands.py nanobot/agent/loop.py tests/test_commands.py tests/test_cli_input.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py
```

Expected: PASS

- [ ] **Step 3: Review final diff**

Run:

```bash
git diff -- \
  nanobot/cli/commands.py \
  nanobot/cli/doctor.py \
  nanobot/agent/loop.py \
  tests/test_commands.py \
  tests/test_cli_input.py \
  tests/test_agentloop_investigation.py \
  tests/test_agentloop_troubleshooting_flow.py \
  README.md \
  README.zh-CN.md \
  docs/development-status-v1.md
```

Verify:
- bootstrap changes stay in CLI boundaries
- onboarding remains minimal
- doctor and quickstart stay bounded
- progress feedback is additive, not a runtime rewrite

- [ ] **Step 4: Commit**

```bash
git add nanobot/cli/commands.py nanobot/cli/doctor.py nanobot/agent/loop.py tests/test_commands.py tests/test_cli_input.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py README.md README.zh-CN.md docs/development-status-v1.md docs/superpowers/plans/2026-03-18-cli-first-install-experience.md
git commit -m "feat: improve cli first-run experience"
```
