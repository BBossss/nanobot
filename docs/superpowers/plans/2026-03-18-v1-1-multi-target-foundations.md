# V1.1 Multi-Target Foundations Implementation Plan

> **给执行该计划的 agent：** 优先使用 `superpowers:subagent-driven-development`，若不可用则使用 `superpowers:executing-plans`。全过程以复选框 `- [ ]` 跟踪。

**目标：** 在保持当前只读安全边界和审计能力不退化的前提下，交付 V1.1 的多目标基础能力：目标分组解析、多目标巡检执行、按目标证据归档与可追溯审计。

**范围：** 本计划仅覆盖 V1.1，不进入 V1.2 的跨主机关联分析。

**技术栈：** Python 3.11+、Pydantic、pytest、pytest-asyncio

---

## 范围决策

In scope:

- 多目标配置模型（targets/groups/labels）与解析
- 巡检路径的多目标批量执行
- 报告与 case 按目标分组输出
- 审计记录补齐目标身份字段
- CLI/IM 输出显式展示目标范围
- 对应回归测试

Out of scope:

- 自动修复执行
- 跨目标时间线关联（V1.2）
- 新增 Web UI

## 文件边界（建议）

优先在现有模块内扩展，避免大范围重构。

可能修改：

- `nanobot/config/schema.py`
- `nanobot/inspection/service.py`
- `nanobot/cases/store.py`
- `nanobot/security/audit.py`
- `nanobot/channels/telegram.py`
- `nanobot/channels/mattermost.py`
- `nanobot/cli/commands.py`

可能新增：

- `nanobot/targets/resolver.py`
- `tests/test_target_resolver.py`
- `tests/test_inspection_multi_target.py`
- `tests/test_audit_target_metadata.py`
- `tests/test_case_multi_target_evidence.py`

---

## 阶段 1：配置与解析（阻塞项）

### 任务 1：扩展配置模型支持多目标分组

- [x] 在 `schema` 中新增 `targets/groups/labels` 结构
- [x] 保持单目标旧配置兼容
- [x] 为非法引用提供清晰报错

验收标准：

- [x] 无效 group->target 引用在启动期失败
- [x] 至少支持 3 个目标组成同一 group

### 任务 2：实现目标解析器（deterministic）

- [x] 新增 `target resolver`：支持显式列表、group、label
- [x] 解析结果稳定有序，便于回归和审计

验收标准：

- [x] 同一输入多次解析结果顺序一致
- [x] 错误输入返回可操作的提示

---

## 阶段 2：多目标巡检执行主链路

### 任务 3：巡检服务支持 N 目标执行

- [x] 将单目标巡检执行升级为多目标迭代执行
- [x] 记录每个目标状态：`ok/failed/skipped`
- [x] 局部失败不阻断整体返回

验收标准：

- [x] 一次请求可完成多目标巡检
- [x] 输出包含每个目标的状态与摘要

### 任务 4：报告按目标与时间窗分组

- [x] 报告结构新增 per-target section
- [x] 保留全局 summary section

验收标准：

- [x] 报告可直接回答“哪个目标在何时出现了什么证据”

---

## 阶段 3：Case 与审计闭环

### 任务 5：Case 记录多目标证据链接

- [x] 同一 incident window 下记录所有目标证据引用
- [x] case 可继续复用当前检索方式

验收标准：

- [x] case 中可定位每个目标的证据路径/片段

### 任务 6：审计补齐目标身份字段

- [x] 审计项包含 `target/executor/command/timestamp/result`
- [x] 兼容既有审计读取逻辑

验收标准：

- [x] 从审计日志可重建单目标动作轨迹

---

## 阶段 4：交互与回归

### 任务 7：CLI / IM 显示目标范围

- [x] 执行前显示解析出的目标范围
- [x] 执行后显示 per-target 成败摘要

验收标准：

- [x] 用户可在结果中确认“实际操作了哪些目标”

### 任务 8：回归测试集补齐

- [x] 新增 resolver / multi-target inspection / audit / case 测试
- [x] 接入当前 CI 流程

验收标准：

- [x] 关键路径回归测试稳定通过

---

## 交付顺序（建议）

1. 配置模型 + 解析器
2. 巡检执行 + 报告分组
3. case + 审计
4. CLI/IM 输出
5. 回归测试与收口

## Definition of Done (V1.1)

- [x] 一条请求可以安全执行多目标巡检
- [x] 报告、case、audit 全链路保留目标身份
- [x] 错误语义明确区分局部失败与全局失败
- [x] CI 覆盖 V1.1 多目标关键路径
