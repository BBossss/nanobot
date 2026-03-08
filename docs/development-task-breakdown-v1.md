# HCI 排障助手 V1 开发任务拆解清单

## 1. 目的

本清单用于将 HCI 排障助手 V1 的现有产品文档与技术方案转化为可执行的开发任务，便于：

- 方案评审
- 排期
- 任务分配
- 后续转 issue

本清单以 V1 为范围，不扩展跨主机执行、高危自动修复、完整 Web UI 等非目标能力。

## 2. 任务拆解原则

### 2.1 优先级原则

开发顺序遵循以下原则：

1. 先锁定安全边界
2. 再实现单机只读排障主链路
3. 再补案例沉淀
4. 再补巡检与报告
5. 最后接入 Mattermost

### 2.2 任务粒度原则

每项任务应满足：

- 能独立评审
- 能独立实现
- 能独立验证

### 2.3 依赖原则

具备强依赖关系的任务必须串行推进，具备弱依赖关系的任务可并行推进。

## 3. 总体阶段划分

V1 建议拆为 6 个阶段：

- 阶段 A：基础收口
- 阶段 B：只读诊断能力
- 阶段 C：案例沉淀与导入
- 阶段 D：巡检与报告
- 阶段 E：Mattermost 接入
- 阶段 F：稳定性与上线准备

补充建议：

当前 V1 主链路已基本落地。若进入下一轮演进，建议新增一个文档与 Skill 优先的阶段：

- 阶段 G：Skill 化收口

## 4. 阶段 A：基础收口

### A1. 文档评审闭环

目标：

- 对当前 PRD、技术设计、白名单、案例、巡检文档进行一次内部评审

输出：

- 评审结论
- 待修改项列表

依赖：

- 无

优先级：

- P0

### A2. Mattermost 调研完成

目标：

- 根据内网 Mattermost 文档补齐待确认清单中的关键信息

输出：

- 明确接入方式
- 明确会话建模方式
- 明确权限模型

依赖：

- [mattermost-integration-open-questions.md](/Users/ruibinhuang/repos/nanobot/docs/mattermost-integration-open-questions.md)

优先级：

- P0

### A3. 命令白名单细化到可执行级

目标：

- 将命令白名单规范细化为实现可直接使用的规则集

输出：

- 精确命令名单
- 每个命令允许的参数模板
- 允许读取的路径前缀
- 审批触发规则

依赖：

- [command-whitelist-spec-v1.md](/Users/ruibinhuang/repos/nanobot/docs/command-whitelist-spec-v1.md)

优先级：

- P0

## 5. 阶段 B：只读诊断能力

### B1. 诊断工具配置模型

目标：

- 在配置层新增诊断工具配置结构

内容：

- `tools.diagnostics.enabled`
- `allowedPaths`
- `maxReadLines`
- `maxSearchHits`
- 可选 `presetChecks`

依赖：

- A3

优先级：

- P0

### B2. 新增受控诊断工具骨架

目标：

- 新增诊断工具模块，替代排障模式下的自由 `exec`

内容：

- `diagnose_log_read`
- `diagnose_log_search`
- `diagnose_system_status`
- `diagnose_preset_check`

依赖：

- B1

优先级：

- P0

### B3. 底层命令模板映射

目标：

- 将诊断工具映射为固定命令模板

内容：

- 文件读取模板
- 关键字搜索模板
- 状态查询模板
- 结果截断与格式化

依赖：

- B2
- A3

优先级：

- P0

### B4. 工具注册与排障模式接线

目标：

- 将新诊断工具注册到 `AgentLoop`
- 明确排障模式下是否暴露通用 `exec`

依赖：

- B2

优先级：

- P0

### B5. 审计日志落盘

目标：

- 所有诊断调用写入独立审计记录

内容：

- 请求来源
- 工具名
- 命令模板
- 参数摘要
- 执行结果摘要

依赖：

- B3

优先级：

- P0

### B6. `/stop` 与卡住请求处理评估

目标：

- 评估并改进当前全局处理锁导致的队头阻塞风险

内容：

- 调研 `AgentLoop` 的全局锁影响
- 评估是否改为按 session 加锁
- 至少补充更清晰的超时与取消策略

依赖：

- 无

优先级：

- P1

说明：

- 该项可作为 V1 中后期稳定性改造，不必阻塞最小链路先落地

## 6. 阶段 C：案例沉淀与导入

### C1. 案例目录与索引初始化

目标：

- 初始化 `notes/cases/` 与 `index.json`

依赖：

- 无

优先级：

- P0

### C2. 案例 ID 与文件命名生成器

目标：

- 实现统一的案例 ID 生成与文件命名规则

依赖：

- C1

优先级：

- P0

### C3. 案例写入服务

目标：

- 将一次排障结果写入标准案例文件

内容：

- frontmatter 写入
- 正文模板填充
- 索引同步更新

依赖：

- C1
- C2

优先级：

- P0

### C4. HISTORY 摘要同步

目标：

- 生成案例时同步向 `HISTORY.md` 追加摘要

依赖：

- C3

优先级：

- P0

### C5. 案例检索服务

目标：

- 支持按关键词、标签、主机、服务等检索案例

依赖：

- C3

优先级：

- P1

### C6. 历史案例导入器

目标：

- 支持导入 Markdown / 文本 / JSON 案例

内容：

- 批量读取
- 元数据抽取
- 转换为统一案例格式
- 索引更新

依赖：

- C3

优先级：

- P1

### C7. CLI 案例命令

目标：

- 补案例相关 CLI

建议子命令：

- `nanobot cases import`
- `nanobot cases list`
- `nanobot cases show`

依赖：

- C5
- C6

优先级：

- P2

## 7. 阶段 D：巡检与报告

### D1. 巡检配置模型

目标：

- 增加巡检目标配置结构

内容：

- `inspection.enabled`
- `reportDir`
- `targets`
- `generateCaseOn`

依赖：

- 无

优先级：

- P0

### D2. 巡检目标采集器

目标：

- 实现针对日志文件、journal、命令检查的输入采集

依赖：

- D1
- B3

优先级：

- P0

### D3. 预过滤与聚合器

目标：

- 对原始输入做关键字过滤、结果裁剪、简单聚合

依赖：

- D2

优先级：

- P0

### D4. 巡检分析服务

目标：

- 将过滤后的结果送入模型生成结构化分析

依赖：

- D3

优先级：

- P0

### D5. 报告生成器

目标：

- 按标准模板输出日报、周报、手动巡检报告

依赖：

- D4

优先级：

- P0

### D6. 巡检结果转案例规则

目标：

- 定义并实现何时由巡检自动生成案例

依赖：

- D5
- C3

优先级：

- P1

### D7. 巡检调度接入 `cron`

目标：

- 使用现有 `CronService` 触发巡检任务

依赖：

- D5

优先级：

- P1

### D8. 巡检失败降级策略

目标：

- 确保模型失败或部分输入失败时仍可输出基础结果

依赖：

- D4
- D5

优先级：

- P1

## 8. 阶段 E：Mattermost 接入

### E1. Mattermost 正式接入设计

目标：

- 基于调研结果补充正式接入设计

依赖：

- A2

优先级：

- P0

### E2. Mattermost 配置模型

目标：

- 在配置层新增 Mattermost channel 配置

依赖：

- E1

优先级：

- P0

### E3. Mattermost channel 实现

目标：

- 实现消息接收、消息发送、权限校验、会话隔离

依赖：

- E2

优先级：

- P0

### E4. ChannelManager 接线

目标：

- 将 Mattermost channel 接入统一渠道管理器

依赖：

- E3

优先级：

- P0

### E5. Mattermost 权限控制

目标：

- 支持 `allowFrom`
- 支持频道或线程级限制（如设计要求）

依赖：

- E3

优先级：

- P1

### E6. Mattermost 结果展示优化

目标：

- 优化 markdown、代码块、长消息拆分、线程回复体验

依赖：

- E3

优先级：

- P1

## 9. 阶段 F：稳定性与上线准备

### F1. 端到端场景验证

目标：

- 覆盖最核心的用户路径

建议场景：

- CLI 发起一次只读排障
- 排障结果生成案例
- 导入一个历史案例
- 手动触发一次巡检并生成报告
- Mattermost 发起排障并收到回复

依赖：

- B、C、D、E 阶段主链路完成

优先级：

- P0

### F2. 错误处理与超时检查

目标：

- 检查模型调用、诊断命令、巡检流程的超时与异常处理

依赖：

- B、D

优先级：

- P0

### F3. 审计与安全回归

目标：

- 校验所有执行路径都遵循命令白名单与审计要求

依赖：

- B5
- E5

优先级：

- P0

### F4. 部署与运行手册

目标：

- 输出安装、启动、日志、升级和常见运维操作说明

依赖：

- 主链路完成

优先级：

- P1

### F5. 示例配置与示例数据

目标：

- 提供最小可运行示例配置与示例案例

依赖：

- B、C、D、E 主链路完成

优先级：

- P1

## 10. 可并行任务建议

以下任务具备较强并行性：

- A2 Mattermost 调研
- B1 诊断配置模型
- C1 案例目录与索引初始化
- D1 巡检配置模型

以下任务可在主链路落地后并行：

- C6 历史案例导入器
- E6 Mattermost 展示优化
- F4 部署与运行手册
- F5 示例配置与示例数据

新增建议：

- G2 Skill 模板规范
- G3 HCI 通用排障 Skill 文档
- G4 巡检分析 Skill 文档

## 11. 最小可运行闭环

如果只做最小闭环，建议先完成以下任务：

- A3 命令白名单细化到可执行级
- B1 诊断工具配置模型
- B2 受控诊断工具骨架
- B3 底层命令模板映射
- B4 工具注册与排障模式接线
- C1 案例目录与索引初始化
- C2 案例 ID 与命名生成器
- C3 案例写入服务
- C4 HISTORY 摘要同步
- D1 巡检配置模型
- D2 巡检目标采集器
- D3 预过滤与聚合器
- D4 巡检分析服务
- D5 报告生成器

完成上述任务后，即可实现：

- 单机只读排障
- 案例沉淀
- 手动或定时巡检
- 自动生成报告

## 12. 建议的 issue 分组

后续转 issue 时，建议按以下分组：

- `epic/security-boundary`
- `epic/diagnostics-tools`
- `epic/case-storage`
- `epic/inspection-reporting`
- `epic/mattermost-channel`
- `epic/stability-release`
- `epic/skillization`

## 13. 阶段 G：Skill 化收口

### G1. Skill 边界确认

目标：

- 明确哪些能力继续保留在主代码
- 明确哪些 HCI 场景逻辑迁移到 Skill

输出：

- Skill 边界说明
- 主代码保留清单
- 后续迁移候选清单

依赖：

- [technical-design-hci-troubleshooting-assistant-v1.md](/Users/ruibinhuang/repos/nanobot/docs/technical-design-hci-troubleshooting-assistant-v1.md)

优先级：

- P0

### G2. Skill 模板规范

目标：

- 定义统一的 `SKILL.md` 模板
- 定义 `references/` 目录规范
- 定义输出结构与风险提示要求

输出：

- Skill 编写规范文档

依赖：

- G1

优先级：

- P0

### G3. HCI 通用排障 Skill 文档

目标：

- 输出 `hci-troubleshooting` Skill 初稿

输出：

- HCI 通用排障 Skill 文档

依赖：

- G2

优先级：

- P0

### G4. 巡检分析 Skill 文档

目标：

- 输出 `hci-inspection-analysis` Skill 初稿

输出：

- 巡检分析 Skill 文档

依赖：

- G2

优先级：

- P1

### G5. 案例总结 Skill 文档

目标：

- 输出 `hci-case-summary` Skill 初稿

输出：

- 案例总结 Skill 文档

依赖：

- G2

优先级：

- P1

### G6. 专项 SOP Skill 文档

目标：

- 输出 `hci-storage-network-sop` Skill 初稿

输出：

- 存储/网络/节点健康 SOP Skill 文档

依赖：

- G2

优先级：

- P2

### G7. Skill 验收清单

目标：

- 定义 Skill 化后的验收标准

输出：

- 稳定性验收点
- 输出结构一致性验收点
- 场景扩展性验收点

依赖：

- G3
- G4
- G5

优先级：

- P1

### G8. 统一执行安全入口设计

目标：

- 收敛所有命令执行路径
- 使巡检与主对话共享同一套执行安全边界

输出：

- 统一执行入口设计说明
- 巡检执行路径收口方案
- 白名单 / 审批 / 审计复用方案

依赖：

- G1

优先级：

- P0

建议子任务：

- G8.1 盘点所有执行路径
- G8.2 定义统一执行治理接口
- G8.3 巡检 `command` 路径收口设计
- G8.4 审计与审批复用设计
- G8.5 安全回归验收清单

### G9. `AgentLoop` 策略层迁出方案

目标：

- 梳理 `AgentLoop` 中的 HCI 业务策略
- 明确迁移到 Skill / policy 的顺序与范围

输出：

- 策略层清单
- 迁移优先级
- 兜底兼容策略

依赖：

- G1
- G3
- G4
- G5

优先级：

- P0

建议子任务：

- G9.1 识别 `AgentLoop` 中的场景策略逻辑
- G9.2 标记平台职责与策略职责边界
- G9.3 定义 Skill / policy 承载方式
- G9.4 设计迁移过程中的兜底策略
- G9.5 定义迁移后的回归验收点

### G10. 存储与配置层收口方案

目标：

- 提升案例存储并发安全性
- 控制配置模型继续膨胀

输出：

- 案例索引原子写或加锁方案
- 路径语义修正规则
- 配置分层与收口建议

依赖：

- G1

优先级：

- P0

建议子任务：

- G10.1 案例索引并发写风险评估
- G10.2 原子写或加锁方案设计
- G10.3 路径语义与 workspace 依赖梳理
- G10.4 配置域拆分建议
- G10.5 配置增长控制原则

## 14. 与现有文档的关系

本任务拆解清单基于以下文档整理：

- [prd-hci-troubleshooting-assistant-v1.md](/Users/ruibinhuang/repos/nanobot/docs/prd-hci-troubleshooting-assistant-v1.md)
- [technical-design-hci-troubleshooting-assistant-v1.md](/Users/ruibinhuang/repos/nanobot/docs/technical-design-hci-troubleshooting-assistant-v1.md)
- [command-whitelist-spec-v1.md](/Users/ruibinhuang/repos/nanobot/docs/command-whitelist-spec-v1.md)
- [case-record-spec-v1.md](/Users/ruibinhuang/repos/nanobot/docs/case-record-spec-v1.md)
- [inspection-and-report-spec-v1.md](/Users/ruibinhuang/repos/nanobot/docs/inspection-and-report-spec-v1.md)
- [mattermost-integration-open-questions.md](/Users/ruibinhuang/repos/nanobot/docs/mattermost-integration-open-questions.md)
