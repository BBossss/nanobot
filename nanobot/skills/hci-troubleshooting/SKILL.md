---
name: hci-troubleshooting
description: HCI 通用排障工作流与输出约束，强调只读优先、证据优先、风险说明。
metadata: {"nanobot":{"always":true}}
---

# HCI Troubleshooting

适用于 HCI 场景下的通用排障对话。

## 工作流

1. 先复述现象和影响范围。
2. 再收集只读证据。
3. 区分已证实事实与推断。
4. 最后给出下一步建议和风险说明。

## 输出结构

回答优先包含：

- 现象
- 已证实证据
- 推断
- 建议动作
- 风险说明

## 工具使用建议

- 优先使用 `diagnose_log_read`、`diagnose_log_search`、`diagnose_system_status`
- 需要历史经验时再使用 `search_cases` / `get_case`
- 需要结构化行动方案时使用 `plan`

## 禁止事项

- 不要在证据不足时直接下结论
- 不要把历史案例当作当前事实
- 不要绕过只读与审批规则
