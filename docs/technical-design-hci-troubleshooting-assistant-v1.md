# HCI 排障助手 V1 技术设计草案

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

#### 建议内容

新增自定义 Skill，例如：

- `workspace/skills/hci-troubleshooting/SKILL.md`

Skill 内容应包含：

- 排障工作流
- 常见日志关键词
- 典型故障类型分类
- 输出格式约束
- 风险边界

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

## 11. 下一步输出物

在本设计草案基础上，建议继续补齐以下文档：

- 命令白名单规范
- 案例文件模板与索引格式定义
- Mattermost 接入设计说明
- 巡检报告模板

