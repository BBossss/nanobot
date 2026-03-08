# HCIGuard 仓库第一轮精简方案（V1）

## 1. 目标

本轮精简只处理两类内容：

1. 本地运行/测试垃圾
2. WhatsApp bridge 整套

本轮**不处理**以下内容：

- 其他 IM 渠道
- 通用 skills
- heartbeat / MCP / web / spawn 等平台能力

原因：

- 先清掉最确定、争议最小的非主线内容
- 避免一次性改动过大，影响当前 HCI 排障主链路稳定性

---

## 2. 精简范围

### 2.1 本地运行/测试垃圾

这些内容不属于产品源码或交付物，应从仓库工作区中清理：

- `.pytest_cache/`
- `tmp/`
- `audit/`
- `brain_backups/`
- `brain_data.db`
- `nohup.out`
- 顶层 `MagicMock...` 目录

说明：

- 这类文件大多来自测试、运行时输出或临时调试。
- 这些内容不应进入后续产品化分支，也不应混入代码评审范围。

### 2.2 WhatsApp bridge 整套

本轮准备下线以下内容：

- `bridge/`
- `nanobot/channels/whatsapp.py`
- `channels login` 对 bridge 的构建/启动入口
- README / SECURITY / docker-compose 中与 WhatsApp bridge 直接相关的说明

说明：

- 当前 HCIGuard 的目标渠道是 CLI、Telegram、Mattermost。
- WhatsApp bridge 是原始 nanobot 的通用渠道能力，不属于当前 HCI 排障场景必需能力。
- 该模块还引入 Node.js 构建链路，会增加维护负担和环境复杂度。

---

## 3. 为什么先删这两类

### 3.1 风险最低

这两类内容和当前 HCI 排障主链路关系最弱：

- 不影响 cases / inspection / diagnostics / approvals / mattermost
- 不影响当前 HCI 文档体系
- 不影响多模型提供商能力

### 3.2 收益明确

删除后可直接带来：

- 更干净的仓库工作区
- 更少的非 Python 运行依赖
- 更少的“这项目到底要不要支持 WhatsApp”的产品噪音

### 3.3 便于后续继续瘦身

第一轮清掉确定项后，第二轮再决定是否继续处理：

- 非目标 IM 渠道
- 非 HCI 通用 skills
- heartbeat / web / MCP / spawn 的收口策略

---

## 4. 具体实施清单

### 4.1 垃圾文件清理

实施动作：

1. 删除本地运行/测试垃圾目录与文件
2. 更新 `.gitignore`（如有必要）
3. 确认这些内容不再被误提交

验收标准：

- `git status` 不再被运行时垃圾污染
- 仓库顶层只保留源码、文档、示例、测试等正式内容

### 4.2 WhatsApp bridge 下线

实施动作：

1. 删除 `bridge/`
2. 删除 `nanobot/channels/whatsapp.py`
3. 从 `schema.py` 中移除 `WhatsAppConfig`
4. 从 `ChannelManager` 中移除 WhatsApp 初始化分支
5. 从 CLI 中移除 `channels login` 和 bridge 构建逻辑
6. 从 README / SECURITY / docker-compose 中移除 WhatsApp bridge 说明
7. 删除对应测试（若存在）

验收标准：

- CLI / gateway 启动不再依赖 bridge
- 配置模型中不再出现 WhatsApp 字段
- README 中不再出现 WhatsApp 接入方式
- 全量测试仍通过

---

## 5. 风险与注意事项

### 5.1 不能只删 `bridge/`

如果只删除 `bridge/`，但保留 `channels login` 和 WhatsApp 配置入口：

- CLI 会留下坏掉的命令
- 文档与实现会不一致
- 用户仍会误以为系统支持 WhatsApp

所以 WhatsApp 相关改动必须作为一组提交完成。

### 5.2 垃圾文件清理不应混入功能改动

建议把“工作区垃圾清理”和“bridge 下线”拆成两个提交：

1. 清理非源码垃圾
2. 下线 WhatsApp bridge

这样回溯和 review 都更清晰。

---

## 6. 本轮之后的候选精简项

不在本轮执行，但后面可以继续评估：

- Discord / Slack / Feishu / DingTalk / QQ / Email / Matrix / Mochat
- 通用 skills（weather / summarize / tmux / clawhub / skill-creator 等）
- 通用个人助理文案与 README 展示内容

---

## 7. 结论

第一轮精简建议非常明确：

1. 先清掉本地运行/测试垃圾
2. 再成组下线 WhatsApp bridge

这是当前最稳、最不容易误伤 HCI 排障主链路的一轮收口动作。
