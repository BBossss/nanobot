# HCI 排障助手联调验收清单（V1）

## 1. 目标

用于现场或预发环境验证以下能力是否可用：

- 只读诊断工具链（日志读取/检索/系统状态）
- 排障案例沉淀与导入
- 巡检扫描、报告生成、定时执行
- 安全控制（只读命令 + 手动放通）
- IM 渠道（Telegram、Mattermost）
- 并发稳定性（单会话卡住不阻塞全局）

---

## 2. 预检

执行：

```bash
nanobot status
```

检查项：

- `Config` 和 `Workspace` 均存在
- 默认模型配置正确
- 目标渠道 `enabled=true` 且 token/base_url 配置完整

---

## 3. 一键 Smoke 验证

仓库根目录执行：

```bash
scripts/run_hci_acceptance.sh --mode quick
```

说明：

- `quick`：本地链路冒烟 + 关键单测
- `full`：额外做 `gateway` 启动探测（需要可用配置）

---

## 4. 功能联调步骤

### 4.1 案例链路

```bash
nanobot cases list --limit 10
nanobot cases import ./legacy_cases
nanobot cases show INC-YYYYMMDD-001
```

通过标准：

- 可列出案例
- 导入后索引更新
- `show` 能查看完整案例正文

### 4.2 巡检与报告链路

```bash
nanobot inspection run --no-llm --trigger manual
```

通过标准：

- 输出 `Inspection done`
- 生成报告文件（`reports/inspection/YYYYMMDD/*.md`）
- 命中异常时可自动生成案例（取决于 `inspection.generateCaseOn`）

### 4.3 定时巡检链路

```bash
nanobot cron add --name "inspection-every-5m" --message "inspection tick" --every-seconds 300
nanobot cron list
```

如果由 Agent 工具创建巡检任务（`add_inspection`），`gateway` 回调应输出：

- `Inspection done: targets=... findings=...`
- `Report: ...`
- 可选 `Case: INC-...`

### 4.4 安全放通链路

配置建议：

- `tools.exec.readonlyMode=true`
- 限定 `tools.exec.allowedCommands`

验证：

```bash
nanobot approvals list
nanobot approvals grant --command "systemctl restart kubelet"
nanobot approvals revoke --command "systemctl restart kubelet"
```

通过标准：

- 非白名单命令被拒绝并提示手工放通
- 放通后可执行，撤销后再次被拒

### 4.5 Telegram 联调

1. 配置 `channels.telegram.enabled=true`、`token`、`allowFrom`
2. 启动 `nanobot gateway`
3. Telegram 发送消息：普通对话 + 触发工具调用

通过标准：

- 消息可收可发
- 无权限用户被拒绝
- 单条消息卡住时，其他会话仍可响应（会话级并发锁）

### 4.6 Mattermost 联调

1. 配置 `channels.mattermost.enabled=true`、`baseUrl`、`token`、`allowFrom`
2. 启动 `nanobot gateway`
3. 在频道/线程中下达排障指令

通过标准：

- WebSocket 入站稳定
- 机器人可在线程中回复（保留 thread 上下文）
- `allowFrom` 生效

---

## 5. 并发与稳定性专项

场景：

- 会话 A 发送长任务（故意耗时）
- 会话 B/C 同时发送短任务

通过标准：

- B/C 不被 A 阻塞
- `/stop` 仅终止对应会话任务

---

## 6. 验收记录模板

每轮联调记录：

- 环境：节点、系统版本、模型提供商
- 时间窗口：开始/结束
- 验收项：通过/失败
- 失败详情：日志片段、报错、复现步骤
- 结论：是否允许上线

---

## 7. 常见问题

- `Matrix` 测试依赖问题：如仅做本项目主链路联调，可先跳过 Matrix 渠道联调。
- `python-olm` 编译失败：不影响 Telegram/Mattermost/CLI 主链路。
- 若 `gateway` 无输出，先检查 token、allowFrom、网络连通性和代理配置。
