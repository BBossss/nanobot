# README Troubleshooting Demo Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a compact troubleshooting-feedback GIF to the README and update user-facing docs to explain the new experience.

**Architecture:** Keep the demo asset deterministic by generating it locally from a fixed terminal-style script, then reference the generated GIF from `README.md`. Update only user-facing documentation that currently lags the implemented troubleshooting feedback behavior.

**Tech Stack:** Python 3.11, standard library, ffmpeg, Markdown

---

## Chunk 1: Demo Asset

### Task 1: Add a deterministic GIF generator

**Files:**
- Create: `scripts/render_troubleshooting_demo_gif.py`
- Create: `assets/demo/troubleshooting-strong-feedback.gif`
- Inspect: `README.md`

- [ ] **Step 1: Write the generator script**

Create a script that renders a terminal-style frame sequence for a fixed troubleshooting transcript and encodes it to GIF.

- [ ] **Step 2: Run the generator locally**

Run:

```bash
python3 scripts/render_troubleshooting_demo_gif.py
```

Expected: `assets/demo/troubleshooting-strong-feedback.gif` is created.

- [ ] **Step 3: Sanity-check the asset**

Verify the GIF dimensions, duration, and that all key feedback moments are visible.

## Chunk 2: README And Docs

### Task 2: Add the GIF to README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a short “see it in action” intro**

Place a short explanation near the troubleshooting example section.

- [ ] **Step 2: Embed the GIF**

Reference `assets/demo/troubleshooting-strong-feedback.gif` with standard Markdown image syntax.

- [ ] **Step 3: Update feature bullets if needed**

Explicitly mention troubleshooting progress feedback in user-facing capability bullets.

### Task 3: Update lagging user-facing docs

**Files:**
- Modify: `docs/hci-feature-guide-v1.md`
- Modify: `docs/hci-troubleshooting-assistant-docs-overview.md`

- [ ] **Step 1: Update the feature guide recent changes**

Add the troubleshooting strong-feedback work and README demo asset.

- [ ] **Step 2: Update the docs overview**

Reference the recent troubleshooting feedback and cluster-aware design docs so readers can find them from the overview.

## Chunk 3: Verification

### Task 4: Verify outputs

**Files:**
- Inspect: `assets/demo/troubleshooting-strong-feedback.gif`
- Inspect: `README.md`
- Inspect: `docs/hci-feature-guide-v1.md`
- Inspect: `docs/hci-troubleshooting-assistant-docs-overview.md`

- [ ] **Step 1: Re-run the GIF generator**

Run:

```bash
python3 scripts/render_troubleshooting_demo_gif.py
```

Expected: GIF generation succeeds without manual steps.

- [ ] **Step 2: Review the README references**

Confirm the image path is correct and the surrounding copy matches the actual demo.

- [ ] **Step 3: Review git diff**

Run:

```bash
git diff -- scripts/render_troubleshooting_demo_gif.py README.md docs/hci-feature-guide-v1.md docs/hci-troubleshooting-assistant-docs-overview.md docs/superpowers/specs/2026-03-18-readme-troubleshooting-demo-design.md docs/superpowers/plans/2026-03-18-readme-troubleshooting-demo.md
```

Expected: only the planned files are changed.
