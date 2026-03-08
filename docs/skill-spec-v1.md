# HCI 排障助手 Skill 规范（V1）

## 1. 目的

本文档用于定义 HCI 排障助手后续 Skill 化演进的统一规范，解决以下问题：

- 哪些能力应该做成 Skill
- `SKILL.md` 应该怎么写
- references 应该怎么组织
- Skill 和主代码、policy 的边界是什么
- 当前建议先落哪几个 Skill

适用对象：

- 技术设计人员
- Skill 编写人员
- 排障场景规则维护人员

---

## 2. Skill 的定位

Skill 是场景方法论层，不是平台基础设施层。

Skill 负责：

- 定义排障流程
- 约束输出结构
- 规范风险提示
- 固化某类场景经验
- 说明何时调用哪些底层工具

主代码负责：

- 渠道接入
- 工具执行
- 安全边界
- 会话与消息流
- 存储与索引
- 巡检执行与定时调度

policy 负责：

- 可配置但不适合写死在 Skill 中的规则
- 例如案例触发模式、默认报告策略、启用哪些 Skill

---

## 3. 适合做成 Skill 的内容

- HCI 通用排障流程
- 存储/网络/节点健康等专项 SOP
- 巡检分析口径
- 报告模板
- 案例总结模板
- 历史案例引用规范
- 特定客户环境的排障方法论

## 4. 不适合做成 Skill 的内容

- Mattermost / Telegram / CLI 渠道实现
- `exec` / diagnostics / cron 等工具实现
- 审批、白名单、审计逻辑
- 案例存储与索引实现
- 会话锁、消息总线、AgentLoop 主循环

判断标准：

- 如果它是所有场景都要复用的平台能力，留在主代码。
- 如果它会因客户环境、产品版本、团队习惯而变化，优先做成 Skill。

---

## 5. V1 推荐 Skill 清单

建议先落 4 个 Skill。

### 5.1 `hci-troubleshooting`

职责：

- 定义 HCI 通用排障主流程
- 统一回答结构
- 强化“先证据、后结论、只读优先”

输入：

- 用户问题
- 当前诊断结果
- 当前会话上下文

输出：

- 现象
- 已证实证据
- 推断
- 下一步建议
- 风险提示

### 5.2 `hci-inspection-analysis`

职责：

- 规范巡检结果解读
- 统一报告结构
- 规范异常等级与建议动作

输入：

- 巡检目标摘要
- 匹配日志
- 采集失败信息

输出：

- 概览
- 重点异常
- 可能原因
- 建议动作

### 5.3 `hci-case-summary`

职责：

- 规范案例沉淀条件
- 规范案例标题、摘要、建议字段
- 区分当前事实与历史经验

输入：

- 当前对话收尾信息
- 当前轮诊断证据
- 可选历史案例引用

输出：

- 标准案例四段式内容
- 统一命名建议
- 统一标签建议

### 5.4 `hci-storage-network-sop`

职责：

- 承载专项排障 SOP
- 覆盖存储、网络、节点健康三类典型问题
- 提供场景化检查建议

输入：

- 故障类型
- 关键日志
- 当前节点状态

输出：

- 推荐检查顺序
- 常见关键词
- 常见根因
- 建议验证动作

---

## 6. 推荐目录结构

建议按如下结构组织：

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

原则：

- 一个 Skill 一个目录
- 入口固定为 `SKILL.md`
- 大段参考资料放 `references/`
- 不把大批配置、脚本、日志样例直接堆进 `SKILL.md`

---

## 7. `SKILL.md` 最小模板

每个 Skill 至少包含以下内容：

```md
---
name: hci-troubleshooting
description: HCI 通用排障流程与输出约束
metadata: |
  {
    "nanobot": {
      "always": false
    }
  }
---

# 目标

说明这个 Skill 用来解决什么问题。

# 适用范围

- 适用于哪些场景
- 不适用于哪些场景

# 输入要求

- 用户应提供哪些信息
- 缺什么信息时应先补采样

# 执行步骤

1. 先确认现象
2. 再采集证据
3. 再给出结论
4. 最后给出下一步建议

# 输出格式

输出必须包含：

- 现象
- 已证实证据
- 推断
- 建议动作
- 风险说明

# 风险边界

- 默认只读
- 不自动执行高风险动作
- 涉及重启/删除/修改配置时必须提示风险

# 调用工具建议

- 优先使用 diagnostics 工具
- 需要历史经验时再查案例
- 不直接扩大执行权限

# 禁止事项

- 不要把推断写成事实
- 不要在证据不足时下定论
- 不要绕过审批机制

# 示例

给出 1~2 个标准输入输出示例。
```

---

## 8. 编写规则

### 8.1 输出规则

统一要求：

- 先证据，后结论
- 区分“已证实 / 推断 / 待确认”
- 建议动作必须说明风险等级
- 不允许省略结论依据

### 8.2 工具使用规则

- Skill 可以建议调用工具
- Skill 不直接实现工具
- Skill 不定义额外执行权限
- Skill 不绕过统一白名单与审批

### 8.3 references 组织规则

适合放进 `references/` 的内容：

- 场景关键词表
- 特定产品日志位置
- 常见根因归纳
- 报告示例
- 客户环境差异说明

不适合放进 `references/` 的内容：

- 大量原始日志
- 临时调试输出
- 实现代码说明

### 8.4 语言与风格规则

- 直接、克制、工程化
- 不写空泛口号
- 不写“可以试试看”式含糊建议
- 建议动作要能落地

---

## 9. Skill 与 policy 的边界

建议边界如下：

- Skill：描述方法论
- policy：描述可配置规则

适合放 policy 的内容：

- 默认启用哪些 Skill
- 哪些渠道默认加载哪些 Skill
- 案例是否自动沉淀
- 巡检报告默认生成策略

适合放 Skill 的内容：

- 如何排障
- 如何总结
- 如何解释巡检结果

---

## 10. V1 推荐启用顺序

建议按以下顺序编写与启用：

1. `hci-troubleshooting`
2. `hci-inspection-analysis`
3. `hci-case-summary`
4. `hci-storage-network-sop`

原因：

- 先稳定通用排障输出
- 再稳定巡检报告
- 再稳定案例沉淀
- 最后补专项 SOP

---

## 11. 验收标准

Skill 文档落地后，至少满足以下标准：

1. 同类问题多轮回答结构基本一致
2. 巡检报告结构不再漂移
3. 案例总结不再依赖主循环中的硬编码策略
4. 新增客户化场景优先通过 Skill 扩展，而不是继续改 `AgentLoop`

---

## 12. 与现有文档的关系

本规范与以下文档配套使用：

- [technical-design-hci-troubleshooting-assistant-v1.md](/Users/ruibinhuang/repos/nanobot/docs/technical-design-hci-troubleshooting-assistant-v1.md)
- [development-task-breakdown-v1.md](/Users/ruibinhuang/repos/nanobot/docs/development-task-breakdown-v1.md)
- [hci-feature-guide-v1.md](/Users/ruibinhuang/repos/nanobot/docs/hci-feature-guide-v1.md)

其中：

- 技术设计文档负责说明为什么要 Skill 化
- 任务拆解文档负责说明按什么顺序做
- 本文档负责说明 Skill 应该具体怎么写
