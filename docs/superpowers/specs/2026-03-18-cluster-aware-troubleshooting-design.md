# Cluster-Aware Troubleshooting With Confirmation Gate 设计

## 1. 目标

本文档定义 HCIGuard 下一阶段在交互式排障上的多节点能力设计。

本阶段目标不是把系统改造成默认多节点排障平台，而是在保持当前单节点体验不变的前提下，让 agent 在必要时能够识别“这可能是集群级问题”，并在获得用户确认后执行跨节点调查。

首版目标：

- 默认仍按单节点模式排障
- agent 能从用户问题中识别潜在的集群/标签范围
- 在扩展到多节点前，先明确说明候选范围并请求确认
- 用户确认后，agent 可以把一组高价值只读调查动作扩展到多个节点
- 输出能够区分共性异常、局部异常、以及未完成采样节点

本阶段不做：

- 默认自动多节点扩查
- 自动根因判定
- 跨节点故障时间线重建
- 大规模并发 SSH 编排优化
- 对所有工具做透明的多节点化改造

## 2. 产品行为

### 2.1 默认行为

如果用户未明确指定多个节点或集群，系统仍然沿用当前单节点排障路径。

这条规则是首版的硬约束，目的是避免因为标签映射、目标组配置或意图识别偏差，导致调查范围被悄悄扩大。

### 2.2 扩查触发条件

当 agent 从用户问题中判断出以下任一信号时，可以提出多节点调查建议：

- 请求中出现明显的集群/分组语义，例如“storage 集群”“整个 HCI 集群”“多台节点都报错”
- 请求中出现服务域或故障域语义，且本地配置中存在可映射的 `targeting.groups` 或 `targeting.targets.labels`
- 当前单节点调查结果显示该问题很可能不是单机局部异常，需要对同类节点做对比采样

### 2.3 确认门

首版引入 `Expansion Confirmation Gate`。

其行为要求：

- agent 在执行多节点调查前，必须先输出候选节点范围
- agent 必须说明扩查依据，例如“根据 storage 标签匹配到以下节点”
- 只有用户明确确认后，才允许进入多节点工具编排
- 若用户拒绝或未确认，则继续使用单节点模式

示例话术：

> 我判断这可能涉及 storage 相关节点。根据当前配置，候选范围是 `node-a`, `node-c`, `node-d`。是否切换到多节点排查？

## 3. 范围与约束

### 3.1 本阶段范围

本阶段只覆盖 `agent troubleshooting` 主链路，不优先改造 `inspection` 作为入口。

但实现上应尽量复用已有多目标基础设施，例如：

- `targeting.targets`
- `targeting.groups`
- `resolve_targets(...)`

### 3.2 首批纳入多节点编排的只读工具

仅以下调查动作纳入首版多节点编排：

- `service_status`
- `process_snapshot`
- `search_log`
- `read_log_tail`
- `find_logs`

原因：

- 这些工具最适合做节点间共性/差异比对
- 输出相对稳定
- 对 SSH 和权限模型的额外要求较低

### 3.3 明确延后项

以下能力在本阶段只做接口预留或完全不做：

- `timeline`
- `root_cause_type`
- 证据时间排序
- 自动汇聚为最终根因
- 跨节点变更建议或自动修复

## 4. 总体架构

首版采用“单节点工具不变，多节点由编排层驱动”的方式落地。

### 4.1 Target Intent Resolver

该组件负责把用户请求中的自然语言意图映射到多节点选择器。

输入：

- 用户请求文本
- 当前会话上下文
- `targeting` 配置

输出：

- 候选 `group_names`
- 候选 `label_all` / `label_any`
- 解析原因 `resolution_reason`
- 是否建议扩展到多节点

首版不追求复杂自然语言理解，只做轻量规则匹配：

- 服务词 -> 标签
- 故障域词 -> 标签
- 直接出现的 group 名 -> group 选择

如果无法稳定解析，则返回“不建议扩展”，继续单节点模式。

### 4.2 Expansion Confirmation Gate

该组件负责把解析结果变成用户可确认的交互动作。

职责：

- 展示候选节点清单
- 展示扩查依据
- 等待用户确认
- 确认后生成会话级的多节点调查上下文

会话级上下文至少包含：

- `resolved_targets`
- `resolution_reason`
- `expansion_confirmed`

### 4.3 Multi-Target Investigation Orchestrator

该组件负责把一次调查动作扩展到多个节点执行。

设计原则：

- 现有 troubleshooting tools 继续保持单节点接口
- orchestrator 对每个节点重复调用单节点工具
- 统一封装输出，确保每条证据都带节点信息

统一输出字段建议至少包含：

- `target_id`
- `target_host`
- `tool_name`
- `status`
- `content`
- `error`

首版可接受串行执行；后续再考虑受控并发。

### 4.4 Evidence Aggregator

该组件负责把多节点结果压缩为更容易被 agent 使用的证据视图。

首版只做三类聚合：

- 共性异常：多个节点都出现
- 局部异常：仅个别节点出现
- 采样失败：SSH 不通、命令失败、权限不足、超时

首版不负责做时间排序，不负责做根因判定。

### 4.5 Progress And Conclusion Formatter

该组件负责把扩查行为清晰反馈给用户。

最低要求：

- 明确说明是否仍处于单节点模式
- 明确说明何时建议扩查
- 明确说明扩查到哪些节点
- 明确区分“共性异常”和“局部异常”
- 明确列出未完成采样节点

## 5. 数据流

### 5.1 单节点默认路径

1. 用户发起普通排障请求
2. agent 按当前默认单节点流程调查
3. 如无多节点信号，保持单节点直到输出结论

### 5.2 多节点扩查路径

1. 用户发起排障请求
2. `Target Intent Resolver` 判断该问题可能涉及某个 group 或 labels
3. `Expansion Confirmation Gate` 输出候选节点并请求确认
4. 用户确认
5. `resolve_targets(...)` 展开为运行时目标集
6. `Multi-Target Investigation Orchestrator` 对选定工具进行 fan-out 调用
7. `Evidence Aggregator` 汇总为共性异常 / 局部异常 / 采样失败
8. agent 基于聚合后的证据继续调查或输出阶段性结论

## 6. 错误处理

### 6.1 目标解析失败

若无法从用户请求稳定映射到任何 group/label：

- 不进入多节点确认流程
- 回退到默认单节点排障
- 在需要时可提示“当前无法自动确定集群范围”

### 6.2 扩展范围过大

自动解析出的候选节点数必须受上限控制。

建议首版默认上限：

- `max_expansion_targets = 5`

当候选超过上限时：

- 确认话术中必须说明已截断
- 或提示用户收窄范围后再执行

### 6.3 部分节点失败

单个节点的失败不能终止整轮多节点调查。

必须记录为节点级失败，并在最终输出中单列：

- 哪些节点未采样成功
- 失败原因是什么

### 6.4 证据冲突

若多个节点表现不一致：

- agent 不得直接下“全集群异常”的结论
- 应明确降级为“存在局部异常，尚不能判定为共享故障”

## 7. 测试策略

### 7.1 目标解析测试

验证点：

- 服务词可以稳定映射到 labels/groups
- 未知意图不会误扩展
- 超过节点上限时会触发截断或提示
- 目标顺序稳定、可重复

### 7.2 多节点编排测试

验证点：

- orchestrator 会对每个目标分别执行工具调用
- 返回结果都带 `target_id`
- 某个节点失败不会影响其他节点结果

### 7.3 输出测试

验证点：

- agent 在建议扩查前会请求确认
- 未确认时不会进入多节点执行
- 已确认后会明确说明扩查节点范围
- 最终输出包含共性异常、局部异常、采样失败三类视图

## 8. 与现有实现的衔接

本设计优先复用以下现有基础：

- [nanobot/targets/resolver.py](/Users/ruibinhuang/repos/nanobot/nanobot/targets/resolver.py)
- [nanobot/config/schema.py](/Users/ruibinhuang/repos/nanobot/nanobot/config/schema.py)
- [nanobot/agent/tools/troubleshooting.py](/Users/ruibinhuang/repos/nanobot/nanobot/agent/tools/troubleshooting.py)
- [nanobot/agent/loop.py](/Users/ruibinhuang/repos/nanobot/nanobot/agent/loop.py)

关键实现原则：

- 不先重写现有单节点工具
- 不把多节点逻辑散落到每个工具内部
- 多节点能力优先收敛在 resolver / confirmation gate / orchestrator / aggregator 这几个边界清晰的单元里

## 9. 成功标准

首版完成后，应满足以下标准：

- 普通请求默认仍按单节点模式运行
- agent 能识别出一部分典型集群级问题的候选范围
- agent 在多节点查询前一定会请求确认
- 用户确认后，agent 能对多个节点执行一组只读调查动作
- 输出能清楚表达共性、差异、失败节点
- 不要求给出最终根因，不要求生成故障时间线

## 10. 后续演进方向

当本阶段稳定后，再继续推进：

1. 时间窗口统一建模与跨节点时间线
2. 候选根因类型输出
3. inspection 与 troubleshooting 共享跨节点证据模型
4. 更细粒度的服务词/标签映射
