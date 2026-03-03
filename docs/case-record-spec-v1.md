# HCI 排障助手 V1 案例记录规范

## 1. 目标

本规范用于定义 HCI 排障助手 V1 中“排障案例”的统一记录方式，确保每次排障结果能够被稳定沉淀、检索、复用和审计。

本规范主要解决以下问题：

- 每次排障记录应保存什么内容
- 案例如何以文件形式统一存储
- 如何为案例建立轻量索引
- 如何导入已有案例库
- 如何区分长期记忆、历史摘要和案例记录

## 2. 适用范围

本规范适用于以下来源生成或导入的案例：

- CLI 手动排障生成的案例
- Mattermost 触发排障生成的案例
- 定时巡检发现异常后生成的案例
- 从历史文档、知识库、FAQ 导入的案例

## 3. 数据分层原则

V1 中，排障相关信息采用分层存储，不应混放在同一个文件中。

### 3.1 长期记忆

文件：

- `memory/MEMORY.md`

用途：

- 保存长期稳定事实
- 保存环境特征、固定约束、常见规则、稳定偏好

不适合存放：

- 单次排障的详细过程
- 大段日志片段
- 临时性事件

### 3.2 历史摘要

文件：

- `memory/HISTORY.md`

用途：

- 追加保存按时间排序的简要摘要
- 支持 grep 快速检索

适合存放：

- 每次排障的一段简短结论摘要
- 巡检发现的异常摘要

### 3.3 案例主记录

目录：

- `notes/cases/`

用途：

- 保存每次排障的详细案例记录
- 保存导入的历史案例
- 作为相似案例匹配和复盘的主数据源

### 3.4 案例索引

文件：

- `notes/cases/index.json`

用途：

- 保存可快速查询的轻量元数据
- 避免每次检索都全量扫描案例文件

## 4. 存储结构

建议采用以下目录结构：

```text
workspace/
  memory/
    MEMORY.md
    HISTORY.md
  notes/
    cases/
      index.json
      INC-20260304-001-storage-io-spike.md
      INC-20260304-002-network-bond-flap.md
  reports/
    daily-2026-03-04.md
```

## 5. 案例记录生命周期

### 5.1 生成

案例可通过以下方式生成：

- 排障任务完成后自动生成
- 巡检发现异常后自动生成
- 用户显式要求记录时生成
- 从已有案例库导入生成

### 5.2 更新

案例允许被补充更新，例如：

- 补写根因
- 补写最终处理结果
- 更新状态（`open` -> `resolved`）

V1 建议使用“覆盖写入 + 同步更新索引”的方式维护。

### 5.3 复用

案例可被后续任务检索和引用，但引用时必须区分：

- 历史案例参考
- 当前任务已确认事实

### 5.4 归档

V1 可暂不实现独立归档机制，默认长期保留案例文件。

## 6. 案例 ID 规范

每个案例必须具有唯一 ID。

建议格式：

- `INC-YYYYMMDD-XXX`

示例：

- `INC-20260304-001`
- `INC-20260304-002`

规则：

- 前缀固定为 `INC`
- 日期使用本地日期
- 当日顺序号三位递增

该 ID 应同时用于：

- frontmatter 中的 `id`
- 索引文件中的主键
- 文件名的一部分

## 7. 文件命名规范

每个案例使用单独文件存储。

建议文件名格式：

- `{id}-{slug}.md`

示例：

- `INC-20260304-001-storage-io-spike.md`
- `INC-20260304-002-cluster-network-flap.md`

要求：

- 文件名使用 ASCII
- `slug` 使用简短英文关键词
- 避免空格与特殊字符

## 8. 案例文件格式

### 8.1 格式要求

V1 统一采用：

- Markdown 正文
- YAML frontmatter 元数据

这样既便于人工阅读，也便于程序提取元数据。

### 8.2 Frontmatter 必填字段

以下字段为必填：

- `id`
- `title`
- `source`
- `created_at`
- `trigger`
- `status`
- `tags`

### 8.3 Frontmatter 建议字段

以下字段建议提供：

- `host`
- `service`
- `severity`
- `root_cause`
- `resolved_at`
- `import_source`

### 8.4 字段定义

- `id`
  案例唯一标识

- `title`
  案例标题，概括问题

- `source`
  案例来源，建议值：
  - `generated`
  - `imported`

- `created_at`
  创建时间，使用 ISO 8601 格式

- `trigger`
  触发方式，建议值：
  - `cli`
  - `mattermost`
  - `scheduled`
  - `import`

- `host`
  排障对象主机名或节点名（如适用）

- `service`
  相关服务或模块

- `severity`
  严重程度，建议值：
  - `low`
  - `medium`
  - `high`
  - `critical`

- `status`
  当前状态，建议值：
  - `open`
  - `monitoring`
  - `resolved`
  - `ignored`

- `root_cause`
  根因状态或简述。未确认时可写 `pending`

- `resolved_at`
  解决时间（如适用）

- `tags`
  标签数组

- `import_source`
  若为导入案例，记录导入来源

### 8.5 正文结构

正文建议采用固定章节，至少包括：

- `# 问题现象`
- `# 检查过程`
- `# 关键证据`
- `# 结论`
- `# 建议`

如有需要可扩展：

- `# 适用环境`
- `# 根因分析`
- `# 处理结果`

### 8.6 标准模板

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
status: open
root_cause: pending
tags:
  - storage
  - io
  - disk
---

# 问题现象

描述用户观察到的现象、告警或报错。

# 检查过程

列出执行过的检查项与诊断步骤摘要。

# 关键证据

记录关键日志片段摘要、命令结果摘要或异常指标。

# 结论

区分已证实事实与高概率推断。

# 建议

给出下一步建议、人工确认项或后续处理方向。
```

## 9. 案例索引规范

### 9.1 目标

`index.json` 用于快速检索，不保存完整正文，只保存检索与展示所需的轻量元数据。

### 9.2 文件格式

建议采用：

- JSON 对象

示例结构：

```json
{
  "version": 1,
  "cases": [
    {
      "id": "INC-20260304-001",
      "title": "存储节点磁盘 IO 异常升高",
      "path": "notes/cases/INC-20260304-001-storage-io-spike.md",
      "source": "generated",
      "created_at": "2026-03-04T10:30:00+08:00",
      "trigger": "mattermost",
      "host": "storage-02",
      "service": "storage",
      "severity": "medium",
      "status": "open",
      "tags": ["storage", "io", "disk"]
    }
  ]
}
```

### 9.3 索引字段

每条索引建议包含：

- `id`
- `title`
- `path`
- `source`
- `created_at`
- `trigger`
- `host`
- `service`
- `severity`
- `status`
- `tags`

### 9.4 一致性要求

案例文件与索引必须保持一致：

- 新增案例时新增索引项
- 更新案例时同步更新索引项
- 删除案例时同步移除索引项（V1 可暂不支持删除）

## 10. HISTORY 摘要写入规范

每次生成案例后，建议同步向 `HISTORY.md` 追加一条简要摘要。

### 10.1 摘要内容

建议包含：

- 时间戳
- 案例 ID
- 主机/对象
- 问题摘要
- 结论摘要

### 10.2 示例

```text
[2026-03-04 10:35] CASE INC-20260304-001 | host=storage-02 | storage IO 异常升高，发现磁盘相关 error 日志，初步判断为磁盘压力导致的性能抖动，建议继续检查底层存储状态。
```

### 10.3 用途

- 快速 grep 检索
- 作为案例入口摘要
- 辅助历史上下文回忆

## 11. 自动生成案例规则

V1 建议在以下条件下自动生成案例：

- 用户主动发起的排障任务结束
- 巡检发现满足阈值的异常
- 诊断结果达到“需要跟进”的级别

### 11.1 不建议自动生成案例的情况

- 没有发现异常
- 信息不足，仅执行了非常浅层检查
- 明显重复且无新增信息的结果

对于这类情况，可只写入 `HISTORY.md` 摘要，不生成新案例文件。

## 12. 导入已有案例规范

### 12.1 导入目标

支持将已有排障案例统一转换为本规范格式。

### 12.2 支持的输入格式

V1 优先支持：

- Markdown
- 文本文件
- JSON（可选）

### 12.3 导入后字段映射

若原始案例结构化程度较低，导入阶段应尽量提取以下信息：

- 标题
- 问题现象
- 适用环境
- 根因
- 处理方式
- 标签
- 来源

无法确定的字段可使用默认值，例如：

- `source: imported`
- `trigger: import`
- `status: resolved` 或 `open`（按来源规则）
- `root_cause: pending`（若未明确）

### 12.4 原始内容保留

对于导入案例，建议：

- 在正文中保留原始内容引用或原文摘录
- 在 frontmatter 中记录 `import_source`

### 12.5 导入去重

V1 可采用基础去重策略：

- 同标题 + 同来源
- 或同标题 + 同时间窗口

V1 不要求复杂相似度去重，但应避免明显重复导入。

## 13. 检索与复用规则

### 13.1 检索优先级

建议采用两级检索：

1. 先查 `index.json`
2. 再按需打开具体案例文件

### 13.2 常用检索维度

- 关键词
- 错误码
- 主机名
- 服务名
- 标签
- 严重程度
- 状态

### 13.3 复用要求

引用历史案例时，系统应：

- 明确标注案例 ID
- 明确标注“历史参考”
- 不将历史案例结论直接当作当前事实

## 14. 不建议放入案例的内容

以下内容不建议直接写入案例正文：

- 未脱敏的凭据
- 私钥、token、密码
- 完整超长原始日志全文
- 无意义的重复命令原始输出

对日志内容应以“片段摘要 + 关键引用”方式保存。

## 15. 与其他文档的关系

本规范应与以下文档配套使用：

- [prd-hci-troubleshooting-assistant-v1.md](/Users/ruibinhuang/repos/nanobot/docs/prd-hci-troubleshooting-assistant-v1.md)
- [technical-design-hci-troubleshooting-assistant-v1.md](/Users/ruibinhuang/repos/nanobot/docs/technical-design-hci-troubleshooting-assistant-v1.md)
- [command-whitelist-spec-v1.md](/Users/ruibinhuang/repos/nanobot/docs/command-whitelist-spec-v1.md)

## 16. V1 后续待细化项

后续仍需继续细化：

- 案例状态流转规则
- 导入器的字段映射细则
- 去重算法策略
- 标签体系标准化
- 报告与案例之间的关联关系

