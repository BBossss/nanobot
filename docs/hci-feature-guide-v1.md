# HCI 排障助手功能文档（基于 nanobot 改造，V1）

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

CLI：

- `nanobot cases list`
- `nanobot cases show <CASE_ID>`
- `nanobot cases import <path>`

核心文件：

- `/Users/ruibinhuang/repos/nanobot/nanobot/cases/store.py`
- `/Users/ruibinhuang/repos/nanobot/nanobot/cases/importer.py`
- `/Users/ruibinhuang/repos/nanobot/nanobot/cli/commands.py`

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

## 4.6 安全控制（命令白名单 + 手工放通）

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

## 4.7 规划与案例学习能力

能力：

- `plan` 工具输出结构化排障计划（quick/full）
- `search_cases` / `get_case` 工具支持 Agent 直接复用历史案例

核心文件：

- `/Users/ruibinhuang/repos/nanobot/nanobot/agent/tools/planning.py`
- `/Users/ruibinhuang/repos/nanobot/nanobot/agent/tools/cases.py`

## 4.8 并发稳定性增强

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

当使用开源聚合平台 CRS 时，建议优先使用 OpenAI 兼容路由：

- 推荐：`/droid/openai`
- 谨慎使用：`/openai`（该路由偏 Responses 形态）

原因：

- 当前 nanobot 的 `custom` provider 使用 OpenAI 兼容 `chat.completions` 方式。
- CRS 的 `/droid/openai` 路由与该模式兼容度更高。

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
      "apiBase": "http://<crs-host>:3000/droid/openai"
    }
  }
}
```

验证步骤：

```bash
nanobot status
nanobot agent -m "回复 ok"
nanobot gateway
```

如 CRS 环境要求额外认证头，可通过 `providers.custom.extraHeaders` 添加。

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
- `/Users/ruibinhuang/repos/nanobot/docs/technical-design-hci-troubleshooting-assistant-v1.md`
- `/Users/ruibinhuang/repos/nanobot/docs/development-task-breakdown-v1.md`
- `/Users/ruibinhuang/repos/nanobot/docs/inspection-and-report-spec-v1.md`
- `/Users/ruibinhuang/repos/nanobot/docs/case-record-spec-v1.md`
- `/Users/ruibinhuang/repos/nanobot/docs/command-whitelist-spec-v1.md`
- `https://github.com/Wei-Shaw/claude-relay-service`
