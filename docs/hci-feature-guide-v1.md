# HCIGuard 功能文档（基于 nanobot 改造，V1）

## 1. 文档目标

本文档用于说明当前仓库中已实现的 HCI 排障助手新增能力，包括：

- 新增了哪些功能
- 这些功能能实现什么
- 如何配置与使用
- 如何测试与验收
- 后续如何扩展

适用对象：

- 排障助手开发者
- 现场实施/运维人员
- 测试与上线负责人

---

## 2. 功能概览（已实现）

当前版本已实现以下能力：

1. 只读诊断工具链
2. 案例沉淀与导入（含检索）
3. 巡检与报告生成
4. 定时巡检调度接入
5. Mattermost 渠道接入
6. 安全控制（只读命令 + 手工放通）
7. 规划能力（结构化排障计划）
8. 案例学习能力（Agent 可检索历史案例）
9. 并发稳定性增强（会话级锁）
10. 联调验收资产（脚本 + 清单）

当前保留的交互入口：

- CLI
- Telegram
- Mattermost

## 2.1 最近更新（本轮）

1. 案例记录策略新增 `cases.recordMode`：
   `every_turn / end_only / manual`，可避免“每轮都落盘”导致案例过密。
2. 默认建议使用 `end_only`：
   仅在“结束/总结/保存”类消息触发自动沉淀，提问类消息不自动沉淀。
3. 工作区模板已升级为 HCI 排障助手身份：
   `AGENTS.md`、`USER.md`、`IDENTITY.md` 默认引导到“只读优先、证据驱动、案例沉淀”。
4. 仓库已完成渠道瘦身：
   当前仅保留 `CLI + Telegram + Mattermost`，已移除与当前 HCI 目标无关的其它 IM 渠道。
5. 排障链路已补充“强反馈”：
   调查前会解释原因，执行中会提示动作与 heartbeat，结论前会补简短过程摘要。
6. README 已新增排障动图：
   用一个短 GIF 直接展示终端里的排障反馈体验。

---

## 3. 架构与流程（新增部分）

### 3.1 消息处理主链路

CLI/IM（Telegram、Mattermost） -> MessageBus -> AgentLoop -> Tools/LLM -> Outbound

### 3.2 案例沉淀链路

任务完成 -> 自动写案例文件（Markdown + frontmatter） -> 更新 `index.json` -> HISTORY 追加摘要

### 3.3 巡检链路

读取巡检目标 -> 预过滤（关键词/裁剪） -> 可选 LLM 分析 -> 生成报告 -> 按规则转案例

### 3.4 定时链路

CronService -> `system_event`（inspection:run） -> 巡检执行 -> 回传巡检摘要/报告路径/案例ID

### 3.5 安全链路

ExecTool readonlyMode 开启后：

- 白名单命令直接执行
- 非白名单命令被拒绝并提示人工放通
- 放通命令保存在 approval 文件

### 3.6 排障反馈链路

`AgentLoop` 复用现有 `on_progress` / bus 通路，将排障过程中的反馈持续发往 CLI 或 IM：

- 固定阶段反馈
- 关键调查动作前的原因说明
- 具体只读动作提示
- 长耗时 heartbeat
- 最终结论前的过程摘要

这条链路不新增独立传输层，仍然沿用现有 progress callback。

---

## 4. 新增功能详解

## 4.1 只读诊断工具

已新增：

- `diagnose_log_read`
- `diagnose_log_search`
- `diagnose_system_status`

能力：

- 限制日志访问路径（防越权）
- 限制读取行数和匹配条数（防爆量）
- 命令超时保护

核心文件：

- `/Users/ruibinhuang/repos/nanobot/nanobot/agent/tools/diagnostics.py`

## 4.2 案例沉淀与导入

能力：

- 自动生成排障案例
- 案例文件标准化存储（Markdown）
- 索引维护（`index.json`）
- 导入 `.md/.txt/.json` 历史案例
- 按关键词/标签/主机/服务检索

当前状态说明：

- 已实现案例导入
- 尚未实现正式的案例导出命令
- 当前如需“导出”，只能手工复制案例目录与 `index.json`

CLI：

- `nanobot cases list`
- `nanobot cases show <CASE_ID>`
- `nanobot cases import <path>`

核心文件：

- `/Users/ruibinhuang/repos/nanobot/nanobot/cases/store.py`
- `/Users/ruibinhuang/repos/nanobot/nanobot/cases/importer.py`
- `/Users/ruibinhuang/repos/nanobot/nanobot/cli/commands.py`

## 4.2.1 案例导出能力规划（待实现）

为了让案例成为真正的平台资产，后续建议补充正式的 `cases export` 能力。

建议目标：

- 支持案例备份
- 支持跨环境迁移
- 支持筛选导出特定案例集合
- 支持后续再导入或离线分析

建议 CLI 形式：

```bash
nanobot cases export <output_dir> \
  [--tag <tag>] \
  [--host <host>] \
  [--service <service>] \
  [--keyword <keyword>] \
  [--status <status>] \
  [--limit <n>] \
  [--format bundle|jsonl]
```

第一版建议默认格式为 `bundle`，导出结构如下：

```text
export-dir/
├── manifest.json
├── index.json
└── cases/
    ├── INC-20260307-001-xxx.md
    ├── INC-20260307-002-xxx.md
    └── ...
```

其中：

- `cases/` 保存原始 Markdown 案例
- `index.json` 保存筛选后的索引
- `manifest.json` 保存导出时间、导出条件、案例数量等元信息

第一版建议只聚焦“案例资产导出”，不混入：

- session 原始对话
- memory 文件
- audit 日志
- inspection 原始报告

这样可以保证导出对象边界清晰，后续再按资产类型补其他导出能力。

## 4.3 巡检与报告

能力：

- 支持巡检目标类型：`log_file` / `journal` / `command`
- 关键词匹配、结果裁剪、错误降级输出
- 生成巡检报告（Markdown）
- 根据 `generateCaseOn` 自动转案例

CLI：

- `nanobot inspection run --no-llm --trigger manual`

核心文件：

- `/Users/ruibinhuang/repos/nanobot/nanobot/inspection/service.py`

## 4.4 定时巡检

能力：

- `cron` 工具支持巡检任务创建（`add_inspection`）
- gateway 回调识别巡检系统事件并执行巡检
- 返回巡检摘要、报告路径、案例 ID

核心文件：

- `/Users/ruibinhuang/repos/nanobot/nanobot/agent/tools/cron.py`
- `/Users/ruibinhuang/repos/nanobot/nanobot/cron/service.py`
- `/Users/ruibinhuang/repos/nanobot/nanobot/cli/commands.py`

## 4.5 Mattermost 接入

能力：

- WebSocket 接收 `posted` 事件
- REST 发送回复
- 线程上下文隔离（thread 会话）
- `allow_from` 权限控制

核心文件：

- `/Users/ruibinhuang/repos/nanobot/nanobot/channels/mattermost.py`
- `/Users/ruibinhuang/repos/nanobot/nanobot/channels/manager.py`

## 4.6 排障过程反馈

能力：

- 排障阶段会持续显示进度，而不是只在最后一次性输出结论
- 调查动作前会补一句“为什么查这一步”
- 长耗时只读调查会输出 heartbeat
- 多节点场景会显示简短进度
- 最终判断前会输出一条简短过程摘要

当前展示位置：

- CLI 终端
- Telegram / Mattermost 渠道中的 progress 消息
- README 动图示例

核心文件：

- `/Users/ruibinhuang/repos/nanobot/nanobot/agent/loop.py`
- `/Users/ruibinhuang/repos/nanobot/nanobot/agent/multi_target.py`
- `/Users/ruibinhuang/repos/nanobot/assets/demo/troubleshooting-strong-feedback.gif`

## 4.7 安全控制（命令白名单 + 手工放通）

能力：

- Exec 只读模式
- 基础白名单命令集
- 精确命令级手工放通/撤销

CLI：

- `nanobot approvals list`
- `nanobot approvals grant --command "..."`
- `nanobot approvals revoke --command "..."`

核心文件：

- `/Users/ruibinhuang/repos/nanobot/nanobot/agent/tools/shell.py`
- `/Users/ruibinhuang/repos/nanobot/nanobot/cli/commands.py`

## 4.8 规划与案例学习能力

能力：

- `plan` 工具输出结构化排障计划（quick/full）
- `search_cases` / `get_case` 工具支持 Agent 直接复用历史案例

核心文件：

- `/Users/ruibinhuang/repos/nanobot/nanobot/agent/tools/planning.py`
- `/Users/ruibinhuang/repos/nanobot/nanobot/agent/tools/cases.py`

## 4.9 并发稳定性增强

能力：

- 从全局处理锁改为会话级锁
- 避免单会话卡住导致全局消息阻塞

核心文件：

- `/Users/ruibinhuang/repos/nanobot/nanobot/agent/loop.py`

---

## 5. 配置说明（重点新增项）

配置文件：`~/.nanobot/config.json`

示例：

```json
{
  "cases": {
    "enabled": true,
    "autoRecord": true,
    "recordMode": "end_only",
    "path": "~/.nanobot/workspace/notes/cases"
  },
  "inspection": {
    "enabled": true,
    "reportDir": "~/.nanobot/workspace/reports/inspection",
    "generateCaseOn": "error",
    "targets": [
      {
        "name": "syslog",
        "kind": "log_file",
        "enabled": true,
        "path": "/var/log/system.log",
        "keywords": ["error", "failed", "panic"],
        "maxLines": 500,
        "maxMatches": 50
      }
    ]
  },
  "tools": {
    "exec": {
      "readonlyMode": true,
      "allowedCommands": ["ls", "cat", "grep", "journalctl", "systemctl"],
      "approvalFile": "~/.nanobot/workspace/approvals/exec_allow.json"
    },
    "diagnostics": {
      "enabled": true,
      "timeout": 20,
      "maxReadLines": 2000,
      "maxSearchHits": 100,
      "allowedPaths": ["/var/log", "/opt/logs"]
    }
  },
  "channels": {
    "mattermost": {
      "enabled": true,
      "baseUrl": "https://mm.example.com",
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

其中 `cases.recordMode` 含义：

- `every_turn`：每轮对话都自动记案例
- `end_only`：仅在结束/总结类消息时自动记案例（推荐）
- `manual`：不自动记案例，改为手动触发

## 5.1 CRS（claude-relay-service）接入说明

当使用 CRS 或类似的 OpenAI-compatible gateway 时，主路径就是现有的 `providers.custom`。
这里不需要单独增加专用 provider；`OpenAI-compatible gateway` 只是通用说法，CRS 只是一个示例。

推荐配置示例：

```json
{
  "agents": {
    "defaults": {
      "provider": "custom",
      "model": "gpt-5-codex"
    }
  },
  "providers": {
    "custom": {
      "apiKey": "cr_xxx",
      "apiBase": "http://<crs-host>:3000/droid/openai/v1"
    }
  }
}
```

如需额外认证头，放在 `providers.custom.extraHeaders` 中。

验证步骤优先使用：

```bash
nanobot doctor
```

如需进一步确认连通性，再使用：

```bash
nanobot agent -m "回复 ok"
nanobot gateway
```

---

## 6. 使用指南

## 6.1 基础运行

```bash
nanobot onboard
nanobot status
nanobot agent
nanobot gateway
```

## 6.2 案例操作

```bash
nanobot cases list --limit 20
nanobot cases show INC-20260307-001
nanobot cases import ./legacy_cases
```

## 6.3 巡检操作

```bash
nanobot inspection run --no-llm --trigger manual
```

## 6.4 定时任务

```bash
nanobot cron add --name "check-every-5m" --message "check logs" --every-seconds 300
nanobot cron list
nanobot cron remove <job_id>
```

## 6.5 安全放通

```bash
nanobot approvals list
nanobot approvals grant --command "systemctl restart kubelet"
nanobot approvals revoke --command "systemctl restart kubelet"
```

---

## 7. 测试与验收

## 7.1 自动化测试

```bash
python3 -m pytest -q
```

当前基线：全量通过（`176 passed`）。

## 7.2 一键验收脚本

```bash
scripts/run_hci_acceptance.sh --mode quick
scripts/run_hci_acceptance.sh --mode full
```

## 7.3 联调清单

参考：

- `/Users/ruibinhuang/repos/nanobot/docs/hci-live-validation-checklist-v1.md`

---

## 8. 扩展开发指南

## 8.1 新增 IM 渠道（通用步骤）

1. 新建 `nanobot/channels/<channel>.py`，实现 `BaseChannel` 的 `start/stop/send`
2. 在配置模型中新增 `<Channel>Config`
3. 在 `ChannelManager` 注册初始化逻辑
4. 在 `channels status` 中新增展示项
5. 增加对应单元测试（入站、出站、权限、线程/会话）

## 8.2 新增技能/工具能力

1. 在 `nanobot/agent/tools/` 新增工具文件
2. 在 `AgentLoop._register_default_tools()` 注册
3. 加参数校验、输出裁剪、超时保护
4. 补测试并加入回归

## 8.3 跨主机方向（建议下一阶段）

建议演进路径：

1. 增加“目标主机抽象层”（SSH/Agent）
2. 工具参数支持 `target_host`
3. 巡检目标支持主机组
4. 报告按主机聚合并生成全局结论

## 8.4 Skill 化扩展方案（推荐）

当前版本已经具备较完整的 HCI 排障底座，但后续新增能力不应继续全部写进主代码。

建议采用：

- 主代码负责“平台能力”
- Skill 负责“场景方法论”

### 8.4.1 哪些能力应该留在主代码

以下内容应继续保留在主代码中：

- IM 渠道适配
- 工具执行引擎
- 只读安全控制与审批
- 案例存储、索引、检索能力
- 巡检执行、定时调度、报告落盘
- 会话管理、并发控制、记忆机制

判断标准：

- 若能力对所有场景都通用
- 若能力需要强约束、强测试、强审计
- 若能力属于系统基础设施

则应保留在主代码。

### 8.4.2 哪些能力更适合做成 Skill

以下内容更适合抽象为 Skill：

- HCI 排障工作流
- 某类故障的 SOP
- 某厂商/某版本的日志位置与关键词知识
- 巡检分析策略与解释口径
- 报告模板与案例总结模板
- 跨主机人工排查流程模板

判断标准：

- 若内容会因客户环境、产品版本、团队习惯而变化
- 若内容本质上是经验规则而不是平台基础设施
- 若内容需要快速迭代且不希望频繁改主代码

则优先做成 Skill。

### 8.4.3 当前已写进主代码、后续建议 Skill 化的部分

建议后续逐步从主代码中抽离出以下“策略层”内容：

1. 巡检分析口径

当前 [service.py](/Users/ruibinhuang/repos/nanobot/nanobot/inspection/service.py) 中已包含固定分析提示词与固定报告章节。
建议改造为：

- 主代码只负责采集、过滤、执行、保存
- Skill 决定“如何分析”和“如何组织报告”

2. 案例生成策略

当前 [loop.py](/Users/ruibinhuang/repos/nanobot/nanobot/agent/loop.py) 中 `_maybe_record_case()` 与 `_should_record_case()` 已包含较强业务语义。
建议改造为：

- 主代码提供 `save_case` 能力
- Skill 决定何时保存、保存什么、如何命名和总结

3. HCI 排障行为约束

当前模板中已经把助手设定为 HCI 排障助手。
后续更建议将“更细的排障流程约束”放到 Skill，而不是继续深入写到主代码逻辑。

4. 历史案例引用策略

`search_cases` / `get_case` 工具应保留在主代码，
但“什么时候搜、搜到后如何引用、如何区分历史经验与当前事实”更适合 Skill 化。

### 8.4.4 推荐 Skill 拆分方案

建议先拆 4 个 Skill：

1. `hci-troubleshooting`

职责：

- 统一 HCI 排障流程
- 约束输出格式
- 强调证据优先、只读优先、风险说明

2. `hci-inspection-analysis`

职责：

- 定义巡检分析步骤
- 统一报告结构
- 规范异常分级与建议动作

3. `hci-case-summary`

职责：

- 规范案例总结格式
- 约束“现象/证据/结论/建议”结构
- 规定何时适合沉淀案例

4. `hci-storage-network-sop`

职责：

- 存储、网络、节点健康等典型故障场景 SOP
- 常见关键词、常见根因、常见验证动作

### 8.4.5 推荐目录结构

建议在 workspace 中按如下组织：

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

### 8.4.6 实施顺序（只动文档与 Skill，不先改主代码）

建议按以下顺序推进：

1. 先定义 Skill 边界

- 明确每个 Skill 的职责、输入、输出、依赖工具
- 明确哪些规则仍保留在主代码

2. 再编写 Skill 初稿

- 先完成 `hci-troubleshooting`
- 再补 `hci-inspection-analysis`
- 再补 `hci-case-summary`
- 最后根据需要补 `hci-storage-network-sop`

3. 再做“主代码兼容 Skill”接线评估

- 确认当前上下文装配逻辑如何加载这些 Skill
- 确认默认启用策略
- 确认是否需要按渠道或场景选择性启用

4. 最后才评估是否迁出主代码中的策略逻辑

- 先保留原逻辑做兜底
- Skill 稳定后，再逐步删除主代码里强业务语义部分

### 8.4.7 每个 Skill 建议包含的内容

每个 Skill 至少包含以下信息：

- 适用场景
- 触发条件
- 输入要求
- 输出格式
- 风险边界
- 调用工具建议
- 禁止事项
- 典型示例

建议统一要求：

- 结论必须区分“已证实 / 推断 / 待确认”
- 优先引用当前诊断证据，其次才引用历史案例
- 涉及写操作、重启、删改配置时必须显式提醒风险

### 8.4.8 推荐验收标准

Skill 化方案完成后，建议至少满足以下验收标准：

1. 排障回答更稳定

- 同类问题多次提问时，输出结构基本一致
- 能稳定包含现象、证据、结论、建议

2. 巡检报告更统一

- 报告结构固定
- 异常分级口径一致
- 建议动作风格一致

3. 案例沉淀更可控

- 非收尾型对话不再频繁产出案例
- 收尾型总结能稳定沉淀为统一格式

4. 主代码复杂度不上升

- 新增 HCI 场景能力优先通过 Skill 实现
- 不再把客户化 SOP 直接写入主代码

### 8.4.9 下一阶段建议

如果下一步仍以文档优先推进，建议继续补两类文档：

1. Skill 拆分实施计划

- 列出每个 Skill 的目标、边界、依赖、验收点

2. Skill 编写规范

- 统一 `SKILL.md` 模板
- 统一 references 目录组织方式
- 统一示例写法与输出格式要求

### 8.4.10 与 Skill 化一起推进的三项架构收口

在推进 Skill 拆分的同时，建议同步落实以下 3 项架构收口原则。
这 3 项不应视为独立优化，而应作为 Skill 化改造的一部分统一推进。

1. 执行安全统一到单一入口

目标：

- 所有命令执行能力都走同一套安全边界
- 巡检不再保留独立的命令执行通道

原则：

- 巡检中的 `command` 类型目标应复用统一执行入口
- 统一只读白名单、审批、超时、审计逻辑
- 禁止出现“主对话一套安全规则，巡检另一套安全规则”的情况

建议落点：

- 主代码保留统一执行引擎
- Skill 只描述“该查什么”，不拥有独立执行权限

2. 策略层从 `AgentLoop` 逐步迁出

目标：

- `AgentLoop` 只保留会话处理、工具调度、消息流转等平台职责
- 场景化排障策略逐步转移到 Skill / policy 层

优先迁出内容：

- 案例自动沉淀触发策略
- 巡检分析口径
- 结论与建议输出模板
- 历史案例引用策略

原则：

- 底座只保留通用能力
- HCI 特有方法论优先通过 Skill 或 policy 配置表达
- 新增客户化规则不再直接写进 `AgentLoop`

3. 存储与配置层做稳

目标：

- 降低并发写入风险
- 防止配置模型继续膨胀失控

存储层建议：

- 案例索引写入增加锁或原子写
- 避免多会话并发写 `index.json` 造成覆盖
- 路径设计不再隐含“必须在 workspace 内”的假设

配置层建议：

- 渠道配置、排障配置、巡检配置分层组织
- 避免单个 schema 文件继续无限增大
- 后续新场景优先放到 Skill / policy，而不是持续堆新的顶层配置项

建议执行顺序：

1. 先补 Skill / policy 边界文档
2. 再梳理统一执行入口设计
3. 再定义存储与配置层收口方案
4. 最后才开始代码级迁移

### 8.4.11 三项收口的实施步骤与验收口径

建议将 3 项收口拆成如下执行步骤。

1. 统一执行安全入口

实施步骤：

- 盘点当前所有执行路径
- 标记哪些路径已受白名单/审批保护
- 将巡检 `command` 目标收敛到统一执行入口
- 统一审计记录格式

验收口径：

- 主对话与巡检执行同一套白名单规则
- 审批逻辑仅保留一套
- 新增执行类能力不再新增第二套命令入口

2. 策略层迁出 `AgentLoop`

实施步骤：

- 先列出 `AgentLoop` 中所有 HCI 业务语义
- 区分“平台职责”和“场景策略”
- 将场景策略先文档化，再 Skill 化
- 保留主代码兜底，分阶段下沉

验收口径：

- `AgentLoop` 不再新增客户化排障规则
- 案例生成、巡检总结、历史案例引用策略均有明确 Skill 或 policy 归属
- 新场景扩展优先通过 Skill 完成

3. 存储与配置层收口

实施步骤：

- 先修复案例索引并发写问题
- 再梳理路径语义与相对路径假设
- 再拆分配置域边界
- 最后控制新配置项只进入必要层级

验收口径：

- 多会话并发写案例时索引不丢失
- cases/report 等目录不强依赖 workspace 内部路径
- 配置文件按领域分层，新增字段增速受控

### 8.4.12 推荐迁移顺序

建议按以下顺序迁移：

1. 先保留现有主代码不动，只新增 Skill 作为流程约束层
2. 再逐步把“巡检分析提示词”和“案例总结策略”从主代码迁到 Skill
3. 最后再评估是否把更细的 HCI 业务规则彻底从主代码移除

原因：

- 先加 Skill 风险最低
- 不会破坏现有测试和运行链路
- 便于逐步验证“Skill 化是否真的提升可维护性”

### 8.4.13 不建议 Skill 化的内容

以下内容不建议抽成 Skill：

- Mattermost / Telegram 渠道实现
- 诊断工具实现
- 案例存储与索引实现
- 巡检执行器与 cron 调度器
- 安全审批机制
- 会话锁与并发控制

这些内容属于平台基础设施，Skill 只应该调用它们，而不应替代它们。

---

## 9. 当前边界与后续建议

已具备：

- 单机排障闭环
- 多模型提供商基础支持
- CLI + Telegram + Mattermost 入口
- 安全控制最小闭环

建议下一步：

1. 做真实 HCI 环境跨主机 PoC（先 2-3 台节点）
2. 标准化巡检规则模板和案例标签体系
3. 增加可视化界面（任务、案例、报告、审批）

---

## 10. 参考文件

- `/Users/ruibinhuang/repos/nanobot/docs/prd-hci-troubleshooting-assistant-v1.md`
- `/Users/ruibinhuang/repos/nanobot/docs/skill-spec-v1.md`
- `/Users/ruibinhuang/repos/nanobot/docs/technical-design-hci-troubleshooting-assistant-v1.md`
- `/Users/ruibinhuang/repos/nanobot/docs/development-task-breakdown-v1.md`
- `/Users/ruibinhuang/repos/nanobot/docs/inspection-and-report-spec-v1.md`
- `/Users/ruibinhuang/repos/nanobot/docs/case-record-spec-v1.md`
- `/Users/ruibinhuang/repos/nanobot/docs/command-whitelist-spec-v1.md`
- `https://github.com/Wei-Shaw/claude-relay-service`
