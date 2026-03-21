# CRS OpenAI-Compatible Gateway Design

**Date:** 2026-03-21
**Status:** Draft for review
**Owner:** Codex

## Goal

Make CRS access a first-class documented path in HCIGuard without adding a new provider type, by standardizing CRS onboarding, doctor guidance, and README examples around the existing `providers.custom` OpenAI-compatible gateway path.

## Problem

HCIGuard already supports direct OpenAI-compatible gateways through `providers.custom`, and the repo already contains a CRS note in `docs/hci-feature-guide-v1.md`. But the main user journey is still incomplete:

- first-run onboarding talks about a generic OpenAI-compatible gateway, but does not explicitly help a CRS operator map that to `providers.custom`
- `doctor` can tell the user that config is incomplete, but the guidance is still too generic for common CRS setup mistakes
- the main README files do not yet contain a concise CRS example config and verification flow

This creates unnecessary friction for a user whose actual deployment path is "use CRS as the model gateway."

## Desired Outcome

After this change, a user who wants to run HCIGuard through CRS should be able to:

1. understand that CRS uses the existing OpenAI-compatible `providers.custom` path
2. complete `nanobot onboard` without wondering whether a dedicated CRS provider is required
3. run `nanobot doctor` and get actionable guidance when `base_url`, `api_key`, `model`, or extra headers are wrong
4. copy a working CRS example from the main docs

## Non-Goals

- No new `providers.crs` config block
- No new `crs` provider implementation
- No CRS-specific runtime branching in the provider registry
- No CRS-only connectivity probe or extra API handshake
- No expansion of onboarding into a multi-provider decision tree
- No changes to troubleshooting logic, tool execution, or agent loop behavior

## Design Principles

- Keep one implementation path for all OpenAI-compatible gateways
- Use `CRS` as an operator-facing example, not as a new internal abstraction
- Improve clarity at the user boundary only: docs, onboarding wording, and doctor feedback
- Preserve troubleshooting-first product positioning by keeping provider setup minimal and deterministic
- Avoid coupling CI or local tests to external CRS availability

## Recommended Approach

Treat CRS as a documented OpenAI-compatible gateway profile on top of the existing `providers.custom` integration.

Why this approach:

- it keeps the provider abstraction simple
- it matches the current codebase, which already has a direct custom provider for OpenAI-compatible endpoints
- it avoids duplicating config, transport, and readiness logic
- it improves the first-run operator experience without risking regressions in the troubleshooting path

## User Experience Flow

Expected operator flow:

1. user reads README or runs `nanobot onboard`
2. onboarding explains that OpenAI-compatible gateways such as CRS should be configured through `providers.custom`
3. user enters `base_url`, `api_key`, and `model`
4. if the CRS deployment requires extra headers, the user adds them under `providers.custom.extraHeaders`
5. user runs `nanobot doctor`
6. doctor reports either:
   - configuration is ready, or
   - which exact field or connection assumption needs attention

## Architecture Boundaries

### Provider Layer

The provider layer remains unchanged.

Relevant boundary:

- `nanobot/providers/custom_provider.py` stays the only direct integration point for CRS-like OpenAI-compatible gateways

This change must not introduce:

- a new provider enum or registry branch
- CRS-specific transport logic
- separate config semantics for CRS

### Onboarding Layer

`nanobot/cli/commands.py` remains the first-run configuration entry point.

This change should:

- keep the current minimal onboarding flow intact
- update wording so the operator understands that "OpenAI-compatible gateway" includes CRS
- continue writing only the existing `providers.custom` fields

This change should not:

- add a new wizard branch for CRS
- request CRS-only fields that are not already supported by config

### Doctor Layer

`nanobot/cli/doctor.py` remains a bounded readiness checker.

This change should:

- keep the existing status model (`ok`, `warning`, `blocked`)
- improve operator-facing guidance for missing or invalid custom provider fields
- mention likely CRS/OpenAI-compatible pitfalls in messages where useful, such as wrong `/v1` path or missing extra headers

This change should not:

- add live CRS-specific probing beyond the existing connectivity contract
- introduce new doctor check categories just for CRS

### Documentation Layer

README files should become the primary operator-facing source for CRS setup.

This change should:

- add a concise CRS example config using `providers.custom`
- explain where `extraHeaders` belongs
- show the recommended verification command `nanobot doctor`

The existing feature guide may be aligned for consistency, but the main success criterion is that the top-level README files are sufficient on their own.

## Content Rules

### README and README.zh-CN

The main docs should add a short, copyable CRS example with:

- `providers.custom.api_base`
- `providers.custom.api_key`
- `providers.custom.model`
- optional `providers.custom.extraHeaders`

They should also explain:

- CRS is configured as an OpenAI-compatible gateway
- no dedicated CRS provider is required
- `nanobot doctor` is the default readiness check after setup

The wording should stay general-first:

- primary phrasing: `OpenAI-compatible gateway`
- example phrasing: `for example, CRS`

### Onboarding Copy

Onboarding copy should remain short and low-friction.

Recommended tone:

- "Configure your OpenAI-compatible gateway (for example, CRS)"

The prompts should not become a mini tutorial. They only need enough specificity to prevent operator confusion about which provider path to use.

### Doctor Guidance

Doctor output should become more actionable, not more verbose.

Recommended message goals:

- if `api_base` is missing, say the OpenAI-compatible gateway base URL is required
- if `api_key` is missing, say the gateway API key is required
- if `model` is missing or invalid, say a model name must be configured for the gateway
- if connectivity fails, suggest checking the gateway path, credentials, and any required extra headers

Messages may mention CRS as an example, but should remain valid for any OpenAI-compatible gateway.

## Failure Handling

This change is guidance-only, so failure handling is mostly about avoiding misleading output.

Rules:

- if docs and CLI wording mention CRS, they must also clearly state that the actual config path is `providers.custom`
- if `doctor` cannot confirm connectivity, it must still preserve the existing bounded failure behavior and not claim CRS-specific diagnosis it cannot prove
- if a deployment uses a non-CRS OpenAI-compatible gateway, the new wording must still read naturally and remain correct

## Testing Strategy

### CLI Tests

Add or update focused tests proving:

- onboarding output makes it clear that the configured path is an OpenAI-compatible gateway and can include CRS
- onboarding still writes the same minimal `providers.custom` config fields as before
- doctor reports blocked status when required custom provider fields are missing, with clearer operator guidance
- doctor reports ok when a minimal custom provider config is ready

### Documentation Verification

Verify manually that:

- README and README.zh-CN contain a consistent CRS example
- the example uses the existing config schema only
- the documented verification step points to `nanobot doctor`

No automated test should depend on external CRS availability.

## File Impact

Expected files for implementation:

- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/hci-feature-guide-v1.md`
- Modify: `nanobot/cli/commands.py`
- Modify: `nanobot/cli/doctor.py`
- Modify: `tests/test_commands.py`

## Open Questions Resolved

- Should CRS be a dedicated provider?
  - No. Reuse `providers.custom`.
- Should the change touch runtime troubleshooting behavior?
  - No. Keep scope to config guidance and readiness messaging.
- Should CRS be the primary product term?
  - No. Keep `OpenAI-compatible gateway` as the primary term and use CRS as an example.

## Recommendation

Proceed with a narrow operator-experience update:

- keep the existing custom provider as the only integration path
- make CRS explicitly discoverable in onboarding and docs
- improve doctor guidance so setup failures are easier to diagnose
- avoid any architecture change that could distract from HCIGuard's first goal: strong troubleshooting capability

This gives CRS users a clear paved path while keeping the codebase and provider model simple.
