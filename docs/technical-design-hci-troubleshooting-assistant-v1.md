# HCIGuard V1 技术设计草案

## 1. 目标

基于 `nanobot` 现有能力，构建一个面向深信服超融合 HCI 场景的 V1 排障助手，实现以下核心目标：

- 提供受控的本机只读排障能力
- 支持日志读取、分析、摘要和结构化结论输出
- 支持沉淀排障案例，并可复用历史案例
- 支持定时巡检与定期报告
- 支持 CLI 与 Mattermost 作为交互入口
- 保持最小权限和高可审计性

V1 不实现任意跨主机执行，不开放高危变更操作。

## 2. 现有能力复用

当前 `nanobot` 已具备以下可复用能力：

- `AgentLoop`：多轮工具调用与任务执行调度
- `MemoryStore`：长期记忆与历史摘要
- `CronService`：定时任务
- `HeartbeatService`：周期性唤醒
- `Channels`：统一 IM 渠道抽象
- `CLI`：本地交互入口
- 多模型提供商支持

对应关键代码：

- [loop.py](/Users/ruibinhuang/repos/nanobot/nanobot/agent/loop.py)
- [memory.py](/Users/ruibinhuang/repos/nanobot/nanobot/agent/memory.py)
- [service.py](/Users/ruibinhuang/repos/nanobot/nanobot/cron/service.py)
- [service.py](/Users/ruibinhuang/repos/nanobot/nanobot/heartbeat/service.py)
- [base.py](/Users/ruibinhuang/repos/nanobot/nanobot/channels/base.py)
- [commands.py](/Users/ruibinhuang/repos/nanobot/nanobot/cli/commands.py)

## 3. V1 总体架构

V1 在现有 `nanobot` 基础上新增 4 个核心层：

- 只读命令执行层
- 排障案例沉淀层
- 巡检与报告层
- Mattermost 渠道层

整体逻辑如下：

1. 用户通过 CLI 或 Mattermost 发起排障请求
2. `AgentLoop` 调用受控的诊断工具而不是自由 shell
3. 诊断工具执行白名单内的只读操作，返回结构化结果
4. Agent 结合当前结果与历史案例生成结构化结论
5. 系统将本次排障沉淀为案例文件与索引摘要
6. 定时任务按计划执行巡检并生成报告

## 4. 模块改造设计

### 4.1 受控只读命令执行层

#### 目标

替代或收敛现有通用 `exec` 工具，避免模型自由执行任意命令。

#### 设计原则

- 模型不直接拼接任意 shell 命令
- 只允许白名单中的只读诊断能力
- 每项能力使用结构化参数
- 所有执行行为可记录审计

#### 实现方案

新增受控诊断工具，例如：

- `diagnose_log_read`
- `diagnose_log_search`
- `diagnose_system_status`
- `diagnose_preset_check`

工具层由 Agent 调用，工具内部再映射到固定命令模板。

示例：

- `diagnose_log_search(path="/var/log/messages", pattern="error", tail_lines=500)`
  映射为受控的 `tail` + `grep` 模板

- `diagnose_system_status(scope="disk")`
  映射为固定只读命令组合

#### 建议代码位置

- 新增目录：`nanobot/agent/tools/diagnostics.py`
- 新增配置：`tools.diagnostics`
- 在 [loop.py](/Users/ruibinhuang/repos/nanobot/nanobot/agent/loop.py) 中注册新工具

#### 与现有 `exec` 的关系

V1 建议：

- 默认不向排障模式暴露自由 `exec`
- 保留现有 `exec`，但仅供开发或受控调试模式使用
- 在排障助手模式下，以诊断工具替代直接 shell 调用

### 4.2 排障案例沉淀层

#### 目标

将每次排障过程沉淀为可复用案例，而不是仅依赖通用记忆文件。

#### 存储结构

建议新增：

- `workspace/notes/cases/`
- `workspace/notes/cases/index.json`

#### 数据分层

- `memory/MEMORY.md`
  仅保存长期稳定事实

- `memory/HISTORY.md`
  仅保存时间序列摘要

- `notes/cases/*.md`
  保存每次排障案例的详细记录

- `notes/cases/index.json`
  保存轻量索引，用于快速检索

#### 案例文件格式

建议采用 Markdown + frontmatter：

```md
---
id: INC-20260304-001
title: 存储节点磁盘 IO 异常升高
source: generated
created_at: 2026-03-04T10:30:00+08:00
trigger: mattermost
host: storage-02
service: storage
severity: medium
tags: [storage, io, disk]
status: open
root_cause: pending
---

# 问题现象
...

# 检查过程
...

# 关键证据
...

# 结论
...

# 建议
...
```

#### 索引结构

`index.json` 最少包含：

- `id`
- `title`
- `path`
- `created_at`
- `source`
- `tags`
- `host`
- `service`
- `severity`
- `status`

#### 实现建议

新增案例存储服务，例如：

- `nanobot/cases/store.py`
- `nanobot/cases/index.py`

职责：

- 生成案例 ID
- 写入案例文件
- 更新索引
- 提供基础检索

### 4.3 现有案例库导入层

#### 目标

支持把已有排障案例快速导入到案例库中。

#### 输入格式

V1 优先支持：

- Markdown
- 文本文件
- 结构化 JSON（可选）

#### 导入流程

1. 读取输入文件
2. 提取或补全元数据
3. 转换为统一案例格式
4. 写入 `notes/cases/*.md`
5. 更新 `index.json`

#### 实现建议

新增导入器：

- `nanobot/cases/importer.py`

并在 CLI 中增加子命令，例如：

- `nanobot cases import <path>`

### 4.4 巡检与报告层

#### 目标

利用现有 `cron` 能力实现定时巡检，并输出报告。

#### 巡检流程

1. 定时触发巡检任务
2. 读取目标日志或执行预定义诊断
3. 先做规则过滤（关键字、错误码、行数限制）
4. 将高价值片段交给模型分析
5. 输出巡检报告
6. 如发现异常，写入巡检记录或案例

#### 设计原则

- 先过滤，再调用模型
- 不将完整大日志直接送入模型
- 报告应采用固定模板

#### 存储建议

新增：

- `workspace/reports/`

报告文件建议按日期命名：

- `daily-2026-03-04.md`
- `weekly-2026-W10.md`

#### 实现建议

新增报告服务：

- `nanobot/reports/generator.py`

新增巡检逻辑封装：

- `nanobot/inspection/service.py`

### 4.5 Mattermost 渠道层

#### 目标

通过 Mattermost 接收排障指令并返回结果。

#### 实现原则

- 复用现有 `BaseChannel`
- 使用频道或线程维度隔离会话
- 与其他渠道一致接入消息总线

#### 建议实现

新增：

- `nanobot/channels/mattermost.py`

并在以下位置接入：

- [schema.py](/Users/ruibinhuang/repos/nanobot/nanobot/config/schema.py)
- [manager.py](/Users/ruibinhuang/repos/nanobot/nanobot/channels/manager.py)
- [commands.py](/Users/ruibinhuang/repos/nanobot/nanobot/cli/commands.py)

#### 会话建议

- 私聊：使用 Mattermost channel id
- 线程：使用 `session_key_override`

建议线程会话键格式：

- `mattermost:{channel_id}:{root_post_id}`

### 4.6 排障 Skill 层

#### 目标

将 HCI 排障流程固化为技能，避免模型无约束自由发挥。

#### 设计定位

Skill 层不替代主代码中的工具、渠道、存储和调度能力，而是在这些底座能力之上补充：

- 场景化排障方法论
- 故障类型知识
- 输出格式约束
- 风险边界约束

即：

- 主代码负责“能做什么”
- Skill 负责“在 HCI 场景下应该怎么做”

#### 适合放到 Skill 的内容

- 排障工作流
- 常见日志关键词与判读规则
- 典型故障类型分类
- 结论输出模板
- 报告模板
- 案例总结模板
- 不同客户环境下的定制 SOP

#### 不适合放到 Skill 的内容

- Mattermost / CLI / Telegram 等渠道接入
- 诊断工具实现
- 案例存储与索引实现
- 巡检调度与报告落盘
- 安全审批机制
- 并发控制与会话管理

这些能力应保持在主代码中，以保证一致性、可测试性和可审计性。

#### 建议 Skill 拆分

V1 后续建议至少拆出 3~4 个 Skill：

1. `workspace/skills/hci-troubleshooting/SKILL.md`

职责：

- 统一 HCI 排障工作流
- 约束输出应包含现象、证据、结论、建议
- 强化“只读优先、证据优先”

2. `workspace/skills/hci-inspection-analysis/SKILL.md`

职责：

- 规范巡检分析流程
- 统一报告结构
- 规范异常分级与结论口径

3. `workspace/skills/hci-case-summary/SKILL.md`

职责：

- 规范案例沉淀时机
- 规范案例标题、摘要、建议字段写法
- 区分“当前事实”和“历史经验”

4. `workspace/skills/hci-storage-network-sop/SKILL.md`

职责：

- 覆盖存储、网络、节点健康等常见故障 SOP
- 提供按场景分类的关键词、验证动作和建议路径

#### 建议目录结构

```text
workspace/skills/
├── hci-troubleshooting/
│   └── SKILL.md
├── hci-inspection-analysis/
│   └── SKILL.md
├── hci-case-summary/
│   └── SKILL.md
└── hci-storage-network-sop/
    ├── SKILL.md
    └── references/
        ├── storage.md
        ├── network.md
        └── node-health.md
```

#### 与当前实现的关系

当前代码中已有一部分“策略层逻辑”写在主代码里，后续建议逐步迁出到 Skill：

- 巡检分析提示词与报告固定章节
- 案例自动沉淀触发策略
- HCI 排障行为约束
- 历史案例引用策略

建议迁移顺序：

1. 先新增 Skill，不动主代码
2. 再逐步将“分析口径”和“总结口径”迁移到 Skill
3. 最后再评估是否移除主代码中较强的业务语义

这样可以降低迁移风险，并保持现有功能稳定。

#### 实施阶段建议

建议按 4 个阶段推进：

1. Skill 设计阶段

- 明确 Skill 边界
- 统一 `SKILL.md` 模板
- 统一输出格式约束

2. Skill 文档落地阶段

- 先写 `hci-troubleshooting`
- 再写 `hci-inspection-analysis`
- 再写 `hci-case-summary`
- 最后按需要扩展 `hci-storage-network-sop`

3. 运行时接线评估阶段

- 确认 Skill 加载顺序
- 确认默认启用策略
- 确认与 workspace 模板的关系

4. 主代码收口阶段

- 保留工具与存储底座
- 逐步缩减主代码中的场景策略
- 避免新场景需求继续进入主代码

#### Skill 最小模板建议

每个 Skill 最少应包含：

- 目标
- 适用范围
- 执行步骤
- 输出结构
- 风险边界
- 调用工具建议
- 典型示例

建议统一要求：

- 先证据，后结论
- 推断必须标注
- 高风险动作只给建议，不自动执行

#### Skill 化后的收益

采用该方案后，预期收益包括：

- HCI 方法论与平台能力解耦
- 客户化场景可通过 Skill 快速定制
- 减少主代码持续膨胀
- 降低后续扩展 Mattermost、跨主机、专项 SOP 时的实现成本

#### 与 Skill 化绑定推进的 3 个架构收口项

Skill 化不应只停留在提示词与工作流文档层，还应同步带动以下 3 个架构收口动作。

1. 统一执行安全入口

要求：

- 所有命令执行都经过同一套只读控制、审批、审计和超时规则
- 巡检服务不再保留独立命令执行通道

设计原则：

- 平台层保留统一执行引擎
- 巡检仅负责定义目标与采集逻辑
- Skill 仅负责定义“查什么”和“怎么解释”，不直接扩展执行权限

2. 将策略层逐步迁出 `AgentLoop`

要求：

- `AgentLoop` 聚焦消息处理、上下文装配、工具调度、会话控制
- HCI 特有策略从主循环中逐步迁移到 Skill / policy 层

优先迁出内容：

- 案例自动生成时机
- 巡检分析口径
- 案例总结模板
- 历史案例引用规则

3. 加固存储与配置层

要求：

- 存储层支持更稳健的并发写入
- 配置层避免继续单文件膨胀

设计原则：

- 案例索引采用锁或原子写
- 路径语义避免硬编码 workspace 内部假设
- 后续场景差异优先进 Skill / policy，而不是持续新增 schema 字段

#### 三项收口的建议落地顺序

建议按以下顺序落地：

1. 先做统一执行安全入口设计

原因：

- 安全边界是底线
- 后续 Skill 化不能建立在双执行入口之上

2. 再做策略层归属梳理

原因：

- 需要先明确哪些逻辑留在平台，哪些迁到 Skill / policy
- 否则 Skill 化范围会持续摇摆

3. 最后做存储与配置层收口

原因：

- 这部分影响面更广
- 适合在边界明确后一次性整理

#### 三项收口的代码层目标

1. 统一执行安全入口

- 最终只保留一个命令执行治理入口
- 白名单、审批、审计、超时在同一处维护
- 巡检服务不再直接持有独立命令执行能力

2. 策略层迁出 `AgentLoop`

- `AgentLoop` 仅保留：
  - 消息处理
  - 上下文装配
  - 工具调度
  - 会话与并发控制
- 场景规则迁移到：
  - Skill
  - policy 配置
  - 独立服务层

3. 存储与配置层收口

- 存储层支持原子写或加锁
- 路径语义支持 workspace 内外统一处理
- 配置层拆为稳定底座配置与场景配置

## 5. 数据流设计

### 5.1 手动排障数据流

1. 用户通过 CLI 或 Mattermost 提出问题
2. Agent 读取当前上下文和相关历史摘要
3. Agent 调用受控诊断工具
4. 工具返回日志片段或状态摘要
5. Agent 形成结构化结论
6. 系统写入：
   - `HISTORY.md` 摘要
   - 案例文件
   - 案例索引

### 5.2 定时巡检数据流

1. `CronService` 触发巡检任务
2. 巡检服务执行预定义检查
3. 发现异常则生成报告
4. 报告写入 `reports/`
5. 如达到阈值，则生成案例并通知用户

## 6. 安全设计

### 6.1 命令执行原则

- 默认拒绝
- 白名单放行
- 参数模板化
- 高危命令硬禁止

### 6.2 审计设计

每次诊断至少记录：

- 时间
- 触发来源
- 请求人
- 使用的诊断工具
- 实际执行的受控命令模板
- 返回摘要

建议审计记录单独存放于：

- `workspace/audit/`

### 6.3 模型输出约束

模型结论必须区分：

- 已证实
- 推断
- 待人工确认

高风险动作只允许输出建议，不允许自动执行。

## 7. 配置设计

建议新增以下配置区域：

### 7.1 诊断配置

```json
{
  "tools": {
    "diagnostics": {
      "enabled": true,
      "allowedPaths": ["/var/log", "/opt/logs"],
      "maxReadLines": 2000,
      "maxSearchHits": 100
    }
  }
}
```

### 7.2 案例存储配置

```json
{
  "cases": {
    "enabled": true,
    "path": "~/.nanobot/workspace/notes/cases",
    "autoRecord": true
  }
}
```

### 7.3 巡检配置

```json
{
  "inspection": {
    "enabled": true,
    "targets": [
      {
        "name": "system-log",
        "path": "/var/log/messages",
        "keywords": ["error", "failed", "critical"]
      }
    ]
  }
}
```

### 7.4 Mattermost 配置

```json
{
  "channels": {
    "mattermost": {
      "enabled": true,
      "serverUrl": "https://mattermost.example.com",
      "token": "...",
      "allowFrom": ["*"]
    }
  }
}
```

## 8. V1 实施顺序

### 阶段 1：单机只读排障 MVP

- 新增受控诊断工具
- 固定结构化输出模板
- 手动触发本机日志排查

### 阶段 2：案例沉淀

- 新增案例文件写入
- 新增案例索引
- 支持导入已有案例

### 阶段 3：巡检与报告

- 定时巡检
- 自动报告生成
- 异常自动沉淀

### 阶段 4：Mattermost 接入

- 新增 Mattermost channel
- 支持在 IM 中触发排障

## 9. 暂不实现内容

- 任意跨主机 SSH 执行
- 自动修复
- 数据库型案例存储
- 完整 Web UI
- 多节点部署编排

## 10. 风险与应对

### 风险 1：日志量过大导致成本高或结论不稳定

应对：

- 前置规则过滤
- 严格限制输入片段大小
- 只对高价值片段调用模型

### 风险 2：模型自由发挥导致误判

应对：

- 使用结构化输出模板
- 引入排障 Skill 约束流程
- 强制区分事实与推断

### 风险 3：命令执行边界不清

应对：

- 先定义白名单规范
- 禁止自由 shell
- 审计所有执行记录

### 风险 4：案例沉淀混乱

应对：

- 强制统一案例模板
- 使用索引文件
- 区分长期记忆与案例记录

### 风险 5：单请求卡住导致后续消息排队

当前 `nanobot` 底座在消息处理层使用全局处理锁，存在“队头阻塞”风险：

- 若某一条请求在模型调用、工具调用或外部依赖处长时间卡住
- 后续消息虽然可被渠道接收，但会在处理阶段排队等待
- 用户侧可能表现为“机器人在线但后续消息不响应”

该问题不仅影响单一 Telegram 会话，理论上会影响共享同一 `AgentLoop` 的其他消息处理。

应对：

- 后续将全局处理锁调整为“按会话加锁”
- 保持同一会话串行，不同会话并行
- 对模型调用和工具调用补充更严格的超时与取消策略
- 保留并强化 `/stop` 作为人工解卡手段

## 11. 下一步输出物

在本设计草案基础上，建议继续补齐以下文档：

- 命令白名单规范
- 案例文件模板与索引格式定义
- Mattermost 接入设计说明
- 巡检报告模板
