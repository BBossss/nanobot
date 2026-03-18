# Troubleshooting Capability Priority Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repository-level agent constraint that makes strong troubleshooting capability the first priority of the project.

**Architecture:** Keep this change intentionally small and local to `AGENTS.md`, where repository operating rules already live. The new rule should explicitly constrain future design tradeoffs without expanding into product messaging, README restructuring, or runtime code changes.

**Tech Stack:** Markdown, repository instructions

---

## Chunk 1: Repository Rule

### Task 1: Add agent-priority guidance to `AGENTS.md`

**Files:**
- Modify: `AGENTS.md`
- Inspect: `docs/superpowers/specs/2026-03-18-troubleshooting-capability-priority-design.md`

- [ ] **Step 1: Read the current `AGENTS.md` placement**

Inspect the current section order and choose a location near the top where project-level priority rules will be seen before architecture and implementation details.

- [ ] **Step 2: Add the new priority section**

Insert a dedicated section such as `## Agent Priority` with wording aligned to the approved spec:

```md
## Agent Priority
- 本项目的第一目标是构建强大的排障能力。
- 任何交互设计、工作流控制、展示优化、文档表达或辅助能力，都不应削弱排障深度、证据质量和调查闭环。
- 当“更强可控性 / 更强展示性 / 更强产品感”和“更强排障能力”发生冲突时，优先保证排障能力。
- 默认优先增强调查能力、证据收集能力、目标感知执行能力和排障结论质量，而不是优先增强表层交互。
```

- [ ] **Step 3: Review wording for overlap**

Check that the new section does not contradict existing architecture notes such as “调查优先，再回退到 `exec`” and does not duplicate lower-level coding-style guidance.

- [ ] **Step 4: Verify the rendered diff**

Run:

```bash
git diff -- AGENTS.md
```

Expected: the diff only adds a focused repository-priority section and does not accidentally rewrite unrelated guidance.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md docs/superpowers/specs/2026-03-18-troubleshooting-capability-priority-design.md docs/superpowers/plans/2026-03-18-troubleshooting-capability-priority.md
git commit -m "docs: prioritize troubleshooting capability in agent guidance"
```

## Chunk 2: Verification

### Task 2: Confirm the rule is scoped correctly

**Files:**
- Inspect: `AGENTS.md`
- Inspect: `README.md`
- Inspect: `README.zh-CN.md`

- [ ] **Step 1: Confirm the rule only affects repository guidance**

Verify that this change lands in `AGENTS.md` only and does not silently expand into README/product copy unless separately requested.

- [ ] **Step 2: Review repository status**

Run:

```bash
git status --short
```

Expected: only the planned instruction/spec/plan files are changed for this task.
