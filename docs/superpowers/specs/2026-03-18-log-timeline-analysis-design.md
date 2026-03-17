# Log Timeline Analysis 设计

## 1. 目标

本文档定义 HCIGuard 下一阶段在多节点排障中的“日志证据时间线”能力设计。

本阶段目标不是改变排障入口，也不是引入严格的时间窗口执行模型，而是在已经采集到的日志证据基础上，抽取可识别的事件时间，并生成一个最小可用的跨节点时间线视图。

首版目标：

- 只处理日志类证据
- 只从 `read_log_tail`、`search_log`、`find_logs` 相关结果中提取时间信息
- 把可识别时间戳的日志行整理成跨节点最小时间线
- 区分“事件时间”和“采样时间”
- 无法提取时间的证据不得强行入时间线

本阶段不做：

- service / journal / system snapshot 时间线
- 严格的时间窗口执行过滤
- 自动根因推理
- 复杂时区换算
- 对缺失日期信息的激进补全

## 2. 产品行为

### 2.1 默认行为

如果当前调查结果中不存在可解析时间戳的日志证据，则系统不生成伪时间线。

应明确输出：

- 没有生成时间线
- 原因是当前证据中没有可解析时间戳

### 2.2 与时间窗口的关系

首版不要求用户必须提供时间窗口。

如果用户没有给时间窗口：

- 系统仍按当前排障流程采集日志证据
- timeline 只基于日志结果内实际解析出的 `event_time` 排序
- 无法解析时保持 `unknown`

因此首版需要明确区分：

- `event_time`：从日志行中解析出来的事件时间
- `observed_at`：本轮 agent 看到这条证据的时间

### 2.3 输出目标

首版 timeline 主要回答三类问题：

- 哪个节点先报错
- 哪些节点在接近时间出现相似异常
- 哪些重要证据没有可用时间信息

## 3. 范围与约束

### 3.1 输入范围

首版只接收已经采集完成的日志文本结果，不负责主动采集。

典型输入来自：

- `read_log_tail`
- `search_log`
- `find_logs` 间接关联出的日志读取结果

### 3.2 明确排除项

以下结果不进入首版 timeline：

- `service_status`
- `process_snapshot`
- `disk_snapshot`
- `network_snapshot`
- `journal_tail`
- 非日志类自由文本结论

### 3.3 时间解析原则

首版采取保守解析策略：

- 能稳定解析才进入 timeline
- 不能稳定解析则标记为 `unknown`
- 不对信息不足的时间字段做强推断

## 4. 总体架构

首版建议新增独立的 timeline 模块，而不是把时间解析逻辑分散到各个工具内部。

### 4.1 Timeline Extractor

该组件负责从日志文本中提取候选事件。

输入：

- `target_id`
- `tool_name`
- 原始日志文本或日志行列表
- 当前采样时间 `observed_at`

输出：

- 事件列表 `timeline_events`

每条事件至少包含：

- `target_id`
- `tool_name`
- `event_time`
- `observed_at`
- `raw_line`
- `normalized_message`
- `time_status`

### 4.2 Timeline Sorter

该组件负责：

- 过滤 `time_status=parsed` 的事件
- 按 `event_time` 排序
- 生成时间线主体

它不负责采集，也不负责根因判断。

### 4.3 Near-Event Grouper

该组件负责识别“时间接近且消息相似”的事件。

首版只做轻量规则：

- 时间差在固定阈值内，例如 5 秒
- `normalized_message` 高度相似或完全一致

输出目标是帮助用户快速看出“这些错误可能是跨节点同时发生的”。

### 4.4 Unknown-Time Collector

该组件负责收集无法解析时间的日志证据。

这些证据不参与排序，但必须单独展示，避免重要日志因为无时间而丢失。

## 5. 时间模型

首版只引入以下核心字段：

- `event_time`
- `observed_at`
- `time_status`

### 5.1 `event_time`

表示日志行中实际发生的事件时间。

规则：

- 成功解析时填标准化时间
- 无法解析时为空

### 5.2 `observed_at`

表示当前 agent 调查时看到这条证据的时间。

它不是故障发生时间，只用于补充上下文。

### 5.3 `time_status`

首版只定义：

- `parsed`
- `unknown`

后续若需要支持更复杂语义，再扩展其他状态。

## 6. 输出结构

首版 timeline 输出建议固定为三段。

### 6.1 Timeline

按 `event_time` 升序展示已解析事件。

每条至少包含：

- 时间
- 节点
- 摘要消息

示例：

```text
10:21:03 node-a timeout while connecting to storage backend
10:21:05 node-b timeout while connecting to storage backend
10:21:08 node-c retry exceeded for storage backend
```

### 6.2 Concurrent / Near Events

展示在接近时间出现的相似异常。

输出目标：

- 不强调绝对排序
- 强调“近同时发生”

### 6.3 No Timestamp Evidence

展示无法解析时间的日志证据。

要求：

- 不进入 Timeline 主体
- 仍保留节点和原始消息

## 7. 错误处理

### 7.1 时间戳解析失败

若单条日志无法解析时间：

- 标记为 `unknown`
- 不进入 Timeline
- 进入 `No Timestamp Evidence`

### 7.2 所有证据都无法解析时间

若当前输入中所有日志都无法提取时间：

- 不生成 Timeline
- 输出明确说明

### 7.3 信息不完整的时间格式

若日志只有时分秒，缺少年月日：

- 首版仅在仓库中已有稳定格式可安全补全时再处理
- 否则保持 `unknown`

### 7.4 排序冲突

若多个事件时间完全一致：

- 保持稳定排序
- 同时保留 `target_id`
- 不强行推断先后关系

## 8. 测试策略

### 8.1 时间戳提取测试

覆盖：

- 常见日志前缀格式能被正确提取
- 无时间戳行返回 `unknown`

### 8.2 时间线排序测试

覆盖：

- 多节点事件按 `event_time` 正确排序
- 排序后保留节点身份

### 8.3 Near-Event 测试

覆盖：

- 两个节点在接近时间出现相似日志时，能进入 `Concurrent / Near Events`

### 8.4 无时间戳回归测试

覆盖：

- 所有证据都无可解析时间时，不生成伪时间线

## 9. 与现有实现的衔接

首版应尽量复用已有多节点基础能力：

- [nanobot/agent/multi_target.py](/Users/ruibinhuang/repos/nanobot/nanobot/agent/multi_target.py)
- [nanobot/agent/loop.py](/Users/ruibinhuang/repos/nanobot/nanobot/agent/loop.py)
- 已有的 `target_id` / `tool_name` 维度

建议以“后处理”的方式接入：

- 先完成日志工具采样
- 再把结果送入 timeline 模块
- 最终把 timeline 摘要附加到多节点结果总结中

## 10. 成功标准

首版完成后，应满足以下标准：

- 能从一部分日志证据中提取事件时间
- 能生成跨节点最小时间线
- 能识别近同时发生的相似事件
- 能保留无法解析时间的证据
- 不要求用户必须先给时间窗口
- 不做根因判断

## 11. 后续演进方向

当本阶段稳定后，再继续推进：

1. 用户显式时间窗口输入
2. service / journal 事件纳入 timeline
3. 更丰富的时间格式解析
4. timeline 与 root-cause candidate 联动
