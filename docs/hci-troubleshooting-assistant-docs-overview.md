# HCI 排障助手 V1 文档总览

## 1. 目的

本文件用于说明 HCI 排障助手 V1 的文档结构、各文档职责、推荐阅读顺序以及后续待补充内容，帮助项目参与者快速建立整体认知。

适用对象：

- 产品负责人
- 技术设计人员
- 开发人员
- 运维与实施人员

## 2. 当前文档清单

当前已整理的核心文档如下：

### 2.1 产品与方案边界

- [HCI 排障助手 V1 PRD](/Users/ruibinhuang/repos/nanobot/docs/prd-hci-troubleshooting-assistant-v1.md)

作用：

- 定义产品目标、范围、非目标、部署边界、核心能力与成功指标

适合回答的问题：

- 这个项目要做什么
- V1 先做什么，不做什么
- 为什么值得做

### 2.2 技术总体设计

- [HCI 排障助手 V1 技术设计草案](/Users/ruibinhuang/repos/nanobot/docs/technical-design-hci-troubleshooting-assistant-v1.md)

作用：

- 将 PRD 进一步落为技术方案，定义模块改造方向、数据流和实施顺序

适合回答的问题：

- 基于 `nanobot` 具体要改哪些模块
- 诊断工具、案例层、巡检层、Mattermost 层怎么组织

### 2.3 Skill 规范

- [HCI 排障助手 Skill 规范（V1）](/Users/ruibinhuang/repos/nanobot/docs/skill-spec-v1.md)

作用：

- 定义哪些能力适合 Skill 化
- 定义 `SKILL.md` 模板、目录结构、编写规则与推荐 Skill 清单

适合回答的问题：

- 哪些逻辑应该从主代码迁出
- HCI 排障 Skill 应该怎么写
- Skill 和主代码、policy 的边界是什么

### 2.4 当前开发状态

- [HCI 排障助手 V1 开发状态清单](/Users/ruibinhuang/repos/nanobot/docs/development-status-v1.md)

作用：

- 汇总当前哪些任务已完成、哪些部分完成、哪些仍待做

适合回答的问题：

- 当前 V1 完成度到哪一步
- 下一轮最该做什么
- 哪些任务已经不需要再重复投入

### 2.5 安全边界

- [HCI 排障助手 V1 命令白名单规范](/Users/ruibinhuang/repos/nanobot/docs/command-whitelist-spec-v1.md)

作用：

- 定义只读命令执行边界，是后续实现诊断工具的安全基线

适合回答的问题：

- 哪些命令可以执行
- 哪些命令需要审批
- 哪些命令必须禁止

### 2.6 知识沉淀与案例体系

- [HCI 排障助手 V1 案例记录规范](/Users/ruibinhuang/repos/nanobot/docs/case-record-spec-v1.md)

作用：

- 定义排障案例如何存储、索引、导入和复用

适合回答的问题：

- 每次排障记录怎么沉淀
- 案例文件和 `index.json` 怎么组织
- 如何导入历史案例库

### 2.7 巡检与报告

- [HCI 排障助手 V1 巡检与报告规范](/Users/ruibinhuang/repos/nanobot/docs/inspection-and-report-spec-v1.md)

作用：

- 定义定时巡检任务、预过滤规则、报告输出和与案例沉淀的关系

适合回答的问题：

- 定时巡检怎么跑
- 什么情况下生成报告
- 什么情况下生成案例

### 2.8 Mattermost 接入调研前置

- [Mattermost 接入待确认项（V1）](/Users/ruibinhuang/repos/nanobot/docs/mattermost-integration-open-questions.md)

作用：

- 在正式设计 Mattermost 接入前，梳理必须确认的环境和能力约束

适合回答的问题：

- 在看内网 Mattermost 文档时该确认什么
- 哪些信息会直接影响最终实现方式

## 3. 推荐阅读顺序

建议按以下顺序阅读和使用文档。

### 第一步：理解产品边界

先阅读：

- [HCI 排障助手 V1 PRD](/Users/ruibinhuang/repos/nanobot/docs/prd-hci-troubleshooting-assistant-v1.md)

目的：

- 明确 V1 范围
- 明确部署形态
- 明确跨主机不是当前重点

### 第二步：理解技术落地方式

再阅读：

- [HCI 排障助手 V1 技术设计草案](/Users/ruibinhuang/repos/nanobot/docs/technical-design-hci-troubleshooting-assistant-v1.md)

目的：

- 明确后续开发应改哪些模块
- 明确实现优先级

### 第三步：理解 Skill 化边界

继续阅读：

- [HCI 排障助手 Skill 规范（V1）](/Users/ruibinhuang/repos/nanobot/docs/skill-spec-v1.md)

目的：

- 明确哪些能力应该抽成 Skill
- 明确 Skill 应如何组织和编写

### 第四步：查看当前开发状态

继续阅读：

- [HCI 排障助手 V1 开发状态清单](/Users/ruibinhuang/repos/nanobot/docs/development-status-v1.md)

目的：

- 明确当前哪些任务已经完成
- 明确下一轮最值得推进的工作

### 第五步：锁定安全边界

然后阅读：

- [HCI 排障助手 V1 命令白名单规范](/Users/ruibinhuang/repos/nanobot/docs/command-whitelist-spec-v1.md)

目的：

- 在任何代码实现前，先固定命令执行边界

### 第六步：理解知识沉淀机制

继续阅读：

- [HCI 排障助手 V1 案例记录规范](/Users/ruibinhuang/repos/nanobot/docs/case-record-spec-v1.md)

目的：

- 明确案例如何沉淀
- 明确历史经验如何复用

### 第七步：理解巡检链路

继续阅读：

- [HCI 排障助手 V1 巡检与报告规范](/Users/ruibinhuang/repos/nanobot/docs/inspection-and-report-spec-v1.md)

目的：

- 明确“定时扫描 -> 分析 -> 报告 -> 案例”的链路

### 第八步：调研外部接入条件

在正式做 IM 接入前阅读：

- [Mattermost 接入待确认项（V1）](/Users/ruibinhuang/repos/nanobot/docs/mattermost-integration-open-questions.md)

目的：

- 带着问题去看内网 Mattermost 文档
- 为后续正式接入设计收集约束

## 4. 文档之间的关系

### 4.1 PRD 是上层边界

PRD 决定：

- 做什么
- 不做什么
- 面向谁
- 交付边界在哪里

其他文档都不应脱离 PRD 单独扩张范围。

### 4.2 技术设计草案承接 PRD

技术设计草案将 PRD 转成技术结构：

- 要改哪些模块
- 数据怎么流动
- 先做哪些模块

### 4.3 Skill 规范承接技术设计

Skill 规范进一步回答：

- 哪些内容应迁出主代码
- Skill 应该如何组织
- 如何避免 Skill 与 policy、主代码职责混淆

### 4.4 开发状态清单承接任务拆解

开发状态清单进一步回答：

- 哪些任务已经完成
- 哪些仍然只是文档完成
- 下一轮最值得做的是什么

### 4.5 命令白名单规范是安全底座

命令白名单规范约束：

- 工具如何实现
- 巡检如何执行
- Mattermost 指令触发后能做什么

它是所有执行相关文档的共同安全边界。

### 4.6 案例记录规范是知识沉淀底座

案例记录规范约束：

- 每次排障如何落档
- 历史案例如何索引
- 导入案例如何统一

它支撑长期复用能力。

### 4.7 巡检与报告规范连接“自动化”与“知识沉淀”

该文档定义：

- 自动巡检的输入边界
- 报告输出形式
- 什么时候把巡检结果转成案例

### 4.8 Mattermost 文档当前仍处于调研前阶段

目前不是最终设计，而是待确认清单。

待拿到内网信息后，应基于该清单补写正式接入设计文档。

## 5. 当前文档体系已覆盖的内容

截至目前，文档体系已经覆盖：

- 产品目标与范围
- 部署边界
- 安全执行边界
- 案例沉淀与导入
- 巡检与报告
- Mattermost 调研清单

这意味着：

- 已经可以开始做方案评审
- 已经可以开始做任务拆解
- 已经具备进入代码实现前的主要前置条件

## 6. 仍待补充的文档

当前仍建议后续补充以下文档：

### 6.1 Mattermost 接入设计说明

前提：

- 完成内网 Mattermost 文档调研

建议内容：

- 接入方式
- 配置项
- 会话建模
- 消息收发流程
- 权限控制
- 重试与去重

### 6.2 部署与运行手册（V1 草案）

建议内容：

- 推荐部署方式
- 启动方式
- 后台运行方式
- 日志位置
- 常见维护动作

### 6.3 任务拆解清单

建议内容：

- 按阶段拆分开发任务
- 标记优先级
- 标记依赖关系

## 7. 建议的下一步

如果当前仍以文档整理为主，建议按以下顺序继续推进：

1. 先调研并确认 Mattermost 环境能力
2. 基于调研结果补正式的 Mattermost 接入设计
3. 补一份部署与运行手册（V1 草案）
4. 再整理开发任务拆解清单

如果准备进入工程实现，建议按以下顺序推进：

1. 先实现受控只读诊断工具
2. 再实现案例文件与索引
3. 再实现巡检与报告
4. 最后接入 Mattermost
