# CLI First 安装与首日体验设计

## 1. 目标

本文档定义 HCIGuard 下一阶段在本机 CLI 场景下的“易安装、易上手、强反馈”体验设计。

本阶段目标不是建设完整安装器，也不是同时覆盖 IM / 平台化部署 / Web UI，而是把产品打造成：

- 一个工程师在自己的机器上可以快速安装
- 第一次运行时不需要先理解复杂配置结构
- 配置完成后可以立刻看到排障价值
- 排障过程中始终有清晰、持续的进度反馈

首版目标：

- 官方唯一推荐安装路径收敛为 `uv tool install nanobot-ai`
- 用户第一次执行 `nanobot` 时，如果缺少最小配置，自动进入交互式向导
- 向导默认只推荐 `OpenAI-compatible` 网关路径
- 首次向导只询问 3 个核心字段：`base_url`、`api_key`、`model`
- 配置完成后自动执行 `doctor` 检查
- CLI 首次真实排障时提供明显的阶段反馈

本阶段不做：

- 自定义安装脚本或复杂 bootstrap 框架
- Homebrew / curl 安装脚本作为主入口
- 首启向导覆盖 Telegram / Mattermost / cron / inspection 全能力
- 完整 Web UI

## 2. 产品定位

本阶段只服务一类核心用户：

- 在本机 CLI 上直接使用的工程师

设计标准不是“能力最全”，而是“5 分钟内跑起来并感知价值”。

## 3. 产品行为

### 3.1 官方安装入口

官方文档、README、首次介绍中的唯一推荐安装方式统一为：

```bash
uv tool install nanobot-ai
```

其他安装方式可以保留，但不作为主叙事，不在首屏优先展示。

### 3.2 首次启动行为

用户执行 `nanobot` 时，CLI 先做最小运行前检查：

- 配置文件是否存在
- workspace 是否存在
- 默认 provider / model 是否可解析

若最小配置缺失，则：

- 不直接报错退出
- 自动进入 onboarding wizard

### 3.3 默认 provider 路径

首版 onboarding 只推荐一条默认路径：

- `OpenAI-compatible` 企业 / 内网网关

向导默认询问：

- `base_url`
- `api_key`
- `model`

其他 provider 保留能力，但收进高级配置，不在首屏打扰用户。

### 3.4 首次成功闭环

向导完成后，CLI 自动执行一次 `doctor` 检查，并给出下一步推荐命令。

最低要求：

- 明确告诉用户配置已写入
- 明确告诉用户当前哪些能力可用
- 直接给出下一条建议命令，例如：
  - `nanobot agent`
  - `nanobot doctor`
  - `nanobot quickstart`

## 4. 范围与约束

### 4.1 本阶段范围

本阶段只覆盖：

- 本机 CLI 安装路径
- 首次配置向导
- 基础可用性检查
- 首次排障中的进度反馈

### 4.2 明确延后项

以下能力不进入首版：

- IM 渠道向导配置
- inspection / cron 的完整首启配置
- 多 provider 并列引导
- 自动修复环境问题
- 系统级依赖自动安装

## 5. 总体架构

首版采用“统一 CLI 入口 + 最小向导 + 可用性检查 + 强反馈执行”的方式落地。

### 5.1 CLI Bootstrap Gate

在 `nanobot` 根命令启动时增加一个轻量 bootstrap gate。

职责：

- 检查最小配置是否存在
- 检查 workspace 是否就绪
- 判断是否需要自动进入 onboarding
- 在首启完成后决定是否继续进入默认命令流程

设计原则：

- 不改变已有命令能力边界
- 只在“缺少最小配置”时拦截
- 该 gate 必须足够轻量，避免成为新一层复杂 runtime

### 5.2 Onboarding Wizard

该组件负责把“首次配置”变成短路径交互。

首版职责：

- 采集 `base_url`
- 采集 `api_key`
- 采集 `model`
- 初始化 `~/.nanobot/config.json`
- 初始化 workspace 和默认模板

设计原则：

- 只写入最小可用配置
- 不要求用户理解完整配置树
- 高级项全部后置

### 5.3 Doctor

该组件负责把“是否真的能跑”明确地告诉用户。

首版至少检查：

- 配置文件是否存在
- workspace 是否存在
- provider 基础字段是否完整
- 默认 model 是否可连通
- 关键目录是否可读写

输出建议固定为结构化状态：

- `配置`
- `工作区`
- `模型连通性`
- `关键目录/权限`

每项状态建议分为：

- `ok`
- `partial`
- `blocked`

### 5.4 Quickstart

该组件负责提供最短可用路径说明，而不是做配置写入。

职责：

- 显示推荐安装方式
- 显示首次配置命令
- 显示最短可运行命令
- 给出 1 到 2 个典型示例

### 5.5 Progress Feedback Layer

该组件负责在真实排障过程中提供持续反馈。

最低要求：

- 显示当前阶段
- 显示正在执行的 tool
- 长时任务时持续有心跳反馈
- 若进入多节点模式，显示节点进度

推荐阶段：

- `初始化上下文`
- `识别目标/范围`
- `生成调查计划`
- `执行只读检查`
- `汇总证据`
- `输出判断`

## 6. 配置模型

### 6.1 首版最小配置

首版向导写入的配置应尽量短，只覆盖默认 agent 可运行所需字段。

建议至少包含：

- `agents.defaults.provider`
- `agents.defaults.model`
- `providers.openai.base_url`
- `providers.openai.api_key`

这里的 `providers.openai` 仅表示配置挂载位置；实际语义为兼容 `OpenAI-compatible` 接口。

### 6.2 高级配置

以下内容不进入首版向导：

- Telegram / Mattermost
- cron
- inspection 扩展配置
- 审批细粒度定制
- 多 provider 并列选择

高级配置继续通过手动编辑配置文件或现有命令完成。

## 7. 用户流

### 7.1 首次安装与运行

1. 用户执行 `uv tool install nanobot-ai`
2. 用户执行 `nanobot`
3. CLI 检查到最小配置缺失
4. 自动进入 onboarding wizard
5. 用户输入 `base_url`、`api_key`、`model`
6. CLI 写入最小配置并初始化 workspace
7. CLI 自动执行 `doctor`
8. CLI 输出检查结果与下一步命令

### 7.2 首次排障

1. 用户执行 `nanobot agent`
2. 系统显示阶段反馈
3. 若需要，显示当前 target / tool / progress
4. 最终输出证据摘要、当前判断与下一步建议

## 8. 错误处理

### 8.1 向导中断

若用户在 onboarding 中途中断：

- 不写入半成品配置
- 明确提示可稍后重新执行 `nanobot` 或 `nanobot onboard`

### 8.2 provider 连通失败

若最小配置写入后无法连通模型：

- 不把结果描述成成功完成
- `doctor` 输出 `blocked`
- 明确指出失败项和下一步，例如检查 `base_url` / `api_key` / 网络连通性

### 8.3 workspace 初始化失败

若目录或权限问题导致 workspace 初始化失败：

- 输出明确错误路径
- 明确指出需要修复的权限或目录问题
- 允许用户后续重跑 `nanobot onboard`

## 9. 命令边界

### 9.1 `nanobot`

职责：

- 默认产品入口
- 执行 bootstrap gate
- 在未配置时自动进入 onboarding

### 9.2 `nanobot onboard`

职责：

- 显式重跑 onboarding wizard
- 更新或重建最小配置

### 9.3 `nanobot doctor`

职责：

- 显示当前环境、配置、连通性、权限状态
- 不修改用户配置

### 9.4 `nanobot quickstart`

职责：

- 展示最短路径和推荐示例
- 不做配置写入

## 10. 测试策略

### 10.1 CLI 首启路径

覆盖：

- 未配置时 `nanobot` 自动进入 onboarding
- 已配置时 `nanobot` 不重复进入 onboarding
- onboarding 完成后能写入最小配置

### 10.2 Doctor

覆盖：

- 缺少配置
- workspace 缺失
- provider 字段缺失
- provider 连通成功 / 失败

### 10.3 Quickstart

覆盖：

- 输出包含官方安装命令
- 输出包含推荐下一步命令

### 10.4 进度反馈

覆盖：

- 首次排障阶段反馈稳定输出
- 多节点模式下能显示进度
- 阻塞状态有明确反馈，不是沉默失败

## 11. 验收标准

本阶段完成的最低标准：

- README 中主安装方式统一为 `uv tool install nanobot-ai`
- 未配置用户执行 `nanobot` 时会自动进入向导，而不是直接报错
- 向导只需填写 `base_url`、`api_key`、`model` 即可完成最小配置
- 向导结束后自动执行一次 `doctor`
- 首次排障时用户能持续看到阶段反馈

## 12. 后续演进

后续可继续扩展但不在本阶段实现：

- 把高级 provider 选择纳入向导
- 增加 demo / 示例故障场景
- 增加环境问题自动修复建议
- 针对 IM / 部署场景提供独立 onboarding 流程
