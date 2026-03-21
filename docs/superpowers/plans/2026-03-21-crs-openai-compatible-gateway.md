# CRS OpenAI-Compatible Gateway Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CRS a clearly supported OpenAI-compatible gateway path in HCIGuard by updating onboarding copy, doctor guidance, and main documentation without adding a new provider type.

**Architecture:** Keep the runtime provider path unchanged and scope the work to user-facing surfaces only. Use `providers.custom` as the single implementation seam, update CLI copy where operators first configure and validate the gateway, and add README examples that explicitly show CRS mapping onto the existing config schema.

**Tech Stack:** Python 3.11+, Typer CLI, pytest, Markdown docs

---

## File Structure

- Modify: `nanobot/cli/commands.py`
  - Responsibility: first-run onboarding prompts and quickstart-adjacent CLI wording.
- Modify: `nanobot/cli/doctor.py`
  - Responsibility: bounded readiness checks and actionable operator-facing doctor details.
- Modify: `tests/test_commands.py`
  - Responsibility: CLI regression coverage for onboarding copy and doctor guidance.
- Modify: `README.md`
  - Responsibility: primary English operator documentation for first-run setup and CRS example config.
- Modify: `README.zh-CN.md`
  - Responsibility: primary Chinese operator documentation for first-run setup and CRS example config.
- Modify: `docs/hci-feature-guide-v1.md`
  - Responsibility: align the existing CRS section with the top-level docs and current CLI wording.

## Chunk 1: CLI Guidance And Regression Coverage

### Task 1: Lock in onboarding copy expectations with failing tests

**Files:**
- Modify: `tests/test_commands.py`
- Reference: `nanobot/cli/commands.py`

- [ ] **Step 1: Add a failing onboarding copy test**

```python
def test_onboard_mentions_crs_as_openai_compatible_gateway(mock_paths):
    result = runner.invoke(
        app,
        ["onboard"],
        input="http://gw.example/v1\nsecret-key\ngpt-4.1-mini\n",
    )

    assert "OpenAI-compatible gateway" in result.stdout
    assert "CRS" in result.stdout
```

- [ ] **Step 2: Run the focused onboarding test to verify it fails**

Run: `python3 -m pytest tests/test_commands.py -k "onboard_mentions_crs" -v`
Expected: FAIL because onboarding currently does not mention CRS.

- [ ] **Step 3: Update onboarding headline copy with the minimal CRS hint**

```python
console.print("[cyan]Configure your OpenAI-compatible gateway (for example, CRS)[/cyan]")
```

- [ ] **Step 4: Re-run the focused onboarding test**

Run: `python3 -m pytest tests/test_commands.py -k "onboard_mentions_crs" -v`
Expected: PASS

- [ ] **Step 5: Re-run the minimal config shape regression**

Run: `python3 -m pytest tests/test_commands.py::test_onboard_writes_minimal_openai_compatible_config -v`
Expected: PASS and the generated config still uses the existing `providers.custom` fields.

- [ ] **Step 6: Commit the onboarding copy change**

```bash
git add tests/test_commands.py nanobot/cli/commands.py
git commit -m "feat: clarify crs onboarding gateway path"
```

### Task 2: Lock in doctor guidance expectations with failing tests

**Files:**
- Modify: `tests/test_commands.py`
- Modify: `nanobot/cli/doctor.py`

- [ ] **Step 1: Add failing doctor guidance tests for missing fields**

```python
def test_doctor_missing_custom_fields_are_operator_friendly(mock_paths):
    result = runner.invoke(app, ["doctor"])

    assert "gateway base URL is required" in result.stdout
    assert "providers.custom" in result.stdout
```

```python
def test_doctor_connectivity_failure_suggests_gateway_path_and_headers(mock_paths):
    config_file, workspace_dir = mock_paths
    config = Config()
    config.agents.defaults.provider = "custom"
    config.agents.defaults.model = "gpt-4.1-mini"
    config.providers.custom.api_base = "http://gw.example/v1"
    config.providers.custom.api_key = "secret-key"
    config_file.write_text(config.model_dump_json(by_alias=True))
    workspace_dir.mkdir(parents=True, exist_ok=True)

    with patch(
        "nanobot.cli.doctor.probe_model_connectivity",
        return_value=("blocked", "upstream timeout"),
    ):
        result = runner.invoke(app, ["doctor"])

    assert "check the gateway path" in result.stdout
    assert "extra headers" in result.stdout
```

- [ ] **Step 2: Run the focused doctor tests to verify they fail**

Run: `python3 -m pytest tests/test_commands.py -k "operator_friendly or gateway_path_and_headers" -v`
Expected: FAIL because doctor currently emits terse generic details.

- [ ] **Step 3: Refine custom-provider doctor details without changing status semantics**

```python
if provider_name == "custom":
    if not provider or not provider.api_base:
        return "blocked", "providers.custom.apiBase is required for your OpenAI-compatible gateway (for example, CRS)"
    if not provider.api_key:
        return "blocked", "providers.custom.apiKey is required for your OpenAI-compatible gateway"
```

```python
if result.finish_reason == "error" or (result.content or "").startswith("Error:"):
    return (
        "blocked",
        "gateway connectivity failed; check base URL, /v1 path, API key, model, and any required extra headers",
    )
```

- [ ] **Step 4: Re-run the focused doctor tests**

Run: `python3 -m pytest tests/test_commands.py -k "operator_friendly or gateway_path_and_headers" -v`
Expected: PASS

- [ ] **Step 5: Run the broader CLI regression slice**

Run: `python3 -m pytest tests/test_commands.py -k "onboard or doctor or quickstart" -v`
Expected: PASS

- [ ] **Step 6: Re-run the ready-state doctor regression**

Run: `python3 -m pytest tests/test_commands.py::test_doctor_reports_ok_when_minimal_custom_provider_is_ready -v`
Expected: PASS and the doctor still reports `ok` for a valid minimal custom gateway setup.

- [ ] **Step 7: Commit the doctor guidance updates**

```bash
git add tests/test_commands.py nanobot/cli/doctor.py
git commit -m "feat: improve crs gateway doctor guidance"
```

## Chunk 2: Operator Documentation Alignment

### Task 3: Add an English README CRS example and validation flow

**Files:**
- Modify: `README.md`
- Reference: `nanobot/cli/commands.py`
- Reference: `nanobot/cli/doctor.py`

- [ ] **Step 1: Add a failing documentation expectation test by inspection**

Check that `README.md` currently lacks a concise CRS example near Quick Start.

Run: `rg -n "CRS|extraHeaders" README.md`
Expected: either no match or no complete Quick Start CRS example.

- [ ] **Step 2: Add the minimal CRS setup section to the Quick Start area**

```md
CRS and similar OpenAI-compatible gateways use the existing `providers.custom` path:

```json
{
  "agents": {
    "defaults": {
      "model": "gpt-4.1-mini",
      "provider": "custom"
    }
  },
  "providers": {
    "custom": {
      "apiBase": "http://crs.example/droid/openai/v1",
      "apiKey": "sk-xxx",
      "extraHeaders": {
        "X-Workspace": "lab"
      }
    }
  }
}
```
```

- [ ] **Step 3: Verify the README now includes the intended operator path**

Run: `rg -n "CRS|providers\\.custom|extraHeaders|nanobot doctor" README.md`
Expected: matches for all of the above in the Quick Start area.

- [ ] **Step 4: Commit the English README update**

```bash
git add README.md
git commit -m "docs: add crs quickstart example"
```

### Task 4: Add the Chinese README CRS example and align the feature guide

**Files:**
- Modify: `README.zh-CN.md`
- Modify: `docs/hci-feature-guide-v1.md`

- [ ] **Step 1: Add the matching Chinese CRS setup guidance**

```md
CRS 这类 OpenAI-compatible 网关沿用现有 `providers.custom` 路径，不需要单独新增 provider。
```

- [ ] **Step 2: Align the feature guide wording with the same operator story**

```md
- 主入口仍是 `providers.custom`
- 如 CRS 需要额外认证头，配置到 `providers.custom.extraHeaders`
- 配置完成后优先执行 `nanobot doctor`
```

- [ ] **Step 3: Verify documentation consistency**

Run: `rg -n "CRS|providers\\.custom|extraHeaders|nanobot doctor" README.zh-CN.md docs/hci-feature-guide-v1.md`
Expected: matching guidance appears in both files with no mention of a dedicated CRS provider.

- [ ] **Step 4: Commit the Chinese docs alignment**

```bash
git add README.zh-CN.md docs/hci-feature-guide-v1.md
git commit -m "docs: align crs gateway setup docs"
```

### Task 5: Run final verification for the full CRS guidance slice

**Files:**
- Modify: `docs/superpowers/plans/2026-03-21-crs-openai-compatible-gateway.md`
- Verify: `tests/test_commands.py`
- Verify: `README.md`
- Verify: `README.zh-CN.md`
- Verify: `docs/hci-feature-guide-v1.md`

- [ ] **Step 1: Run the full command test file**

Run: `python3 -m pytest tests/test_commands.py -v`
Expected: PASS

- [ ] **Step 2: Run the full test suite**

Run: `python3 -m pytest -q`
Expected: PASS

- [ ] **Step 3: Update the plan checklist as work completes**

Mark completed steps in this plan file so the execution state stays current.

- [ ] **Step 4: Commit the final verification state if the plan file changed**

```bash
git add docs/superpowers/plans/2026-03-21-crs-openai-compatible-gateway.md
git commit -m "docs: sync crs gateway implementation plan status"
```
