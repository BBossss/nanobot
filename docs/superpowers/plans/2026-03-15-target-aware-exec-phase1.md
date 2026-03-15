# 面向 `target` 的 `exec` 第一阶段实现计划

> **给执行该计划的 agent：** 必须优先使用 `superpowers:subagent-driven-development`（如果当前环境支持 subagent），否则使用 `superpowers:executing-plans`。计划步骤统一使用复选框 `- [ ]` 进行跟踪。

**目标：** 把当前 `exec` 升级为支持 `target` 参数和 SSH 内部执行模式的排障执行底座，并保留只读边界与审计能力。

**实现思路：** 本计划只覆盖设计文档中的 Phase 1 子项目，不试图一次完成全部调查动作和连续调查逻辑。实现方式是在现有 `ExecTool` 上增加 `target` 感知、最小 SSH 传输支持、密码型 SSH 的进程内输入/传递能力，以及配套配置和回归测试；不引入独立 SSH tool，不让模型自己拼整条 `ssh ...` 命令字符串。

**技术栈：** Python 3.11+、Typer、Pydantic、asyncio subprocess、pytest、pytest-asyncio

---

## 范围决策

原始设计文档覆盖多个后续阶段，包括：

- 面向 `target` 的 `exec` / SSH 内部执行模式
- 调查动作工具
- AgentLoop 连续调查缓存
- 收敛规则

这些内容不适合放进一份首轮实现计划。  
本计划只覆盖最先产出可执行价值的子项目：

- 增强版 `exec`
- `target` 参数
- SSH 内部执行模式
- 密码型 SSH 的最小可用实现
- 审计与持久化回归

后续的调查动作层和 `AgentLoop` 连续调查逻辑应另写单独计划。

## 文件结构

本计划涉及的文件边界如下。

### 需要修改的现有文件

- `nanobot/agent/tools/shell.py`
  - 继续作为 `exec` 工具入口
  - 增加 `target` 参数解析
  - 路由到本地执行或 SSH 执行
  - 保留当前超时、输出裁剪、审计、guard 行为
- `nanobot/config/schema.py`
  - 为 `exec` 增加面向 `target` / SSH 的相关配置
  - 增加默认调查轮数保护参数 `max_investigation_rounds`
- `tests/test_exec_readonly_approval.py`
  - 保留并扩展只读边界回归
  - 补充面向 `target` 的 `exec` 配置和 guard 行为验证
- `tests/test_commands.py`
  - 补充配置序列化/CLI 接线回归（如需要）

### 需要新增的文件

- `nanobot/agent/tools/exec_transport.py`
  - 只负责执行层细节
  - 包含 target 解析、SSH 命令封装、密码输入传递、结果标准化
  - 不放排障语义
- `tests/test_exec_target_aware.py`
  - 覆盖本机/远程目标执行分流
  - 覆盖 target 参数解析
- `tests/test_exec_ssh_password.py`
  - 覆盖密码型 SSH 的最小可用行为
  - 覆盖密码不进入返回文本/审计正文/持久化路径

### 文件职责说明

- `shell.py` 保持对外接口稳定，避免把 `ExecTool` 膨胀成一个过大的本地/远程/密码/审计混合文件。
- `exec_transport.py` 只负责“怎么执行”，不负责“排障要查什么”。
- 调查动作工具不在本计划中实现，避免范围膨胀。

## 阶段 1：配置与传输骨架

### 任务 1：定义面向 `target` 的 `exec` 配置与传输边界

**涉及文件：**
- 新增：`nanobot/agent/tools/exec_transport.py`
- 修改：`nanobot/config/schema.py`
- 测试：`tests/test_exec_target_aware.py`

- [x] **步骤 1：先写会失败的测试，覆盖配置默认值与 `target` 解析**

```python
from nanobot.config.schema import ExecToolConfig
from nanobot.agent.tools.exec_transport import ExecTarget, parse_exec_target


def test_exec_tool_config_exposes_target_aware_defaults() -> None:
    cfg = ExecToolConfig()

    assert cfg.default_target == "local"
    assert cfg.max_investigation_rounds == 8
    assert cfg.ssh.enabled is True


def test_parse_exec_target_for_local() -> None:
    target = parse_exec_target("local")

    assert target.kind == "local"
    assert target.host == ""


def test_parse_exec_target_for_remote_host() -> None:
    target = parse_exec_target("root@example-host:2222")

    assert target.kind == "ssh"
    assert target.username == "root"
    assert target.host == "example-host"
    assert target.port == 2222
```

- [x] **步骤 2：运行新增测试，确认当前实现确实失败**

运行：

```bash
pytest tests/test_exec_target_aware.py -v
```

预期：

- 报出 `nanobot.agent.tools.exec_transport` 的 `ModuleNotFoundError`
- 或提示缺少 `default_target`、`ssh` 等配置属性

- [x] **步骤 3：补齐最小配置模型和传输层数据结构**

实现内容：

- 在 `nanobot/config/schema.py` 中增加 `SSHExecConfig`
- 在 `ExecToolConfig` 中增加 `default_target: str = "local"`
- 在 `ExecToolConfig` 中增加 `max_investigation_rounds: int = 8`
- 在 `ExecToolConfig` 中增加 `ssh: SSHExecConfig`
- 在 `nanobot/agent/tools/exec_transport.py` 中增加 `ExecTarget` dataclass
- 在 `nanobot/agent/tools/exec_transport.py` 中实现 `parse_exec_target()`

最小 `target` 对象结构：

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecTarget:
    kind: str
    host: str = ""
    port: int = 22
    username: str = ""
```

- [x] **步骤 4：重新运行聚焦测试**

运行：

```bash
pytest tests/test_exec_target_aware.py -v
```

预期：

- 配置默认值相关断言通过
- 本地 `target` 解析断言通过
- 远程 `target` 解析断言通过

- [x] **步骤 5：运行现有的配置相关回归测试**

运行：

```bash
pytest tests/test_commands.py tests/test_tool_validation.py -v
```

预期：

- 测试通过
- 现有配置行为没有回归

- [x] **步骤 6：提交本阶段改动**

```bash
git add nanobot/config/schema.py nanobot/agent/tools/exec_transport.py tests/test_exec_target_aware.py
git commit -m "feat: add target-aware exec config skeleton"
```

## 阶段 2：本地与 SSH 执行分流

### 任务 2：在不改变工具公开名称的前提下，让 `ExecTool` 按本地或 SSH 路径执行

**涉及文件：**
- 修改：`nanobot/agent/tools/shell.py`
- 修改：`nanobot/agent/tools/exec_transport.py`
- 测试：`tests/test_exec_target_aware.py`
- 测试：`tests/test_exec_readonly_approval.py`

- [x] **步骤 1：先写会失败的测试，覆盖 `target` 感知后的执行分流**

补充类似下面的测试：

```python
import pytest

from nanobot.agent.tools.shell import ExecTool


@pytest.mark.asyncio
async def test_exec_runs_local_when_target_is_local(tmp_path):
    tool = ExecTool(working_dir=str(tmp_path))
    result = await tool.execute(command="printf 'ok'", target="local")

    assert "ok" in result


@pytest.mark.asyncio
async def test_exec_rejects_raw_ssh_in_command_string(tmp_path):
    tool = ExecTool(working_dir=str(tmp_path))
    result = await tool.execute(command="ssh root@example-host 'uptime'", target="local")

    assert "Use target=" in result
```

另外增加一个基于 `monkeypatch` 的传输分流测试：

```python
@pytest.mark.asyncio
async def test_exec_routes_remote_target_to_ssh_transport(tmp_path, monkeypatch):
    tool = ExecTool(working_dir=str(tmp_path))

    async def fake_run_remote(*, target, command, timeout, env):
        return "remote-ok"

    monkeypatch.setattr(tool, "_run_remote_command", fake_run_remote)
    result = await tool.execute(command="uptime", target="root@example-host")

    assert result == "remote-ok"
```

- [x] **步骤 2：运行聚焦测试，确认当前分流逻辑尚未实现**

运行：

```bash
pytest tests/test_exec_target_aware.py::test_exec_runs_local_when_target_is_local \
       tests/test_exec_target_aware.py::test_exec_rejects_raw_ssh_in_command_string \
       tests/test_exec_target_aware.py::test_exec_routes_remote_target_to_ssh_transport -v
```

预期：

- 由于 `ExecTool.execute()` 尚未接受 `target` 而失败
- 或由于执行分流辅助逻辑尚不存在而失败

- [x] **步骤 3：为 `ExecTool` 增加面向 `target` 的执行分流**

在 `nanobot/agent/tools/shell.py` 中实现：

- 在工具 schema 中增加 `target`
- 让 `execute()` 接受 `target`
- 使用 `parse_exec_target()` 解析目标
- 保留对破坏性命令的 guard 检查
- 当 `target="local"` 时，拒绝裸写 `ssh ...` 命令字符串，引导模型使用结构化 `target`
- 拆分执行路径为：
  - `_run_local_command(...)`
  - `_run_remote_command(...)`

`execute()` 应继续作为唯一的公开入口。

- [x] **步骤 4：实现最小可用的 SSH 传输执行辅助逻辑**

在 `nanobot/agent/tools/exec_transport.py` 中实现：

- SSH 命令参数构造
- `target` 归一化
- 如有需要，补充结果标准化辅助逻辑

暂时不要为跳板机、交互式 PTY、凭据租约系统做优化。

- [x] **步骤 5：重新运行聚焦的执行分流测试**

运行：

```bash
pytest tests/test_exec_target_aware.py -v
```

预期：

- 本地 `target` 执行断言通过
- 远程 `target` 分流断言通过
- 裸写 `ssh` 命令字符串会被拒绝

- [x] **步骤 6：重新运行只读 guard 回归测试**

运行：

```bash
pytest tests/test_exec_readonly_approval.py tests/test_exec_dialog_guard.py -v
```

预期：

- 测试通过
- 危险命令依然会被阻止

- [x] **步骤 7：提交本阶段改动**

```bash
git add nanobot/agent/tools/shell.py nanobot/agent/tools/exec_transport.py tests/test_exec_target_aware.py tests/test_exec_readonly_approval.py
git commit -m "feat: route exec through target-aware local and ssh execution"
```

## 阶段 3：密码型 SSH、审计脱敏与持久化安全

### 任务 3：在运行进程内支持密码型 SSH，同时避免敏感信息泄漏到持久化路径

**涉及文件：**
- 修改：`nanobot/agent/tools/shell.py`
- 修改：`nanobot/agent/tools/exec_transport.py`
- 测试：`tests/test_exec_ssh_password.py`
- 测试：`tests/test_loop_save_turn.py`
- 测试：`tests/test_commands.py`

- [x] **步骤 1：先写会失败的测试，覆盖密码型 SSH 行为**

补充类似下面的测试：

```python
import json
import pytest

from nanobot.agent.tools.shell import ExecTool


@pytest.mark.asyncio
async def test_exec_remote_password_is_not_echoed_in_result(tmp_path, monkeypatch):
    tool = ExecTool(working_dir=str(tmp_path))

    async def fake_remote(*, target, command, timeout, env):
        assert env["NANOBOT_SSH_PASSWORD"] == "secret-123"
        return "ok"

    monkeypatch.setattr(tool, "_run_remote_command", fake_remote)
    result = await tool.execute(
        command="uptime",
        target="root@example-host",
        ssh_password="secret-123",
    )

    assert "secret-123" not in result


@pytest.mark.asyncio
async def test_exec_remote_password_is_redacted_from_audit(tmp_path, monkeypatch):
    tool = ExecTool(working_dir=str(tmp_path))

    async def fake_remote(*, target, command, timeout, env):
        return "ok"

    monkeypatch.setattr(tool, "_run_remote_command", fake_remote)
    await tool.execute(command="uptime", target="root@example-host", ssh_password="secret-123")

    payload = json.loads((tmp_path / "audit" / "commands.jsonl").read_text().splitlines()[-1])
    assert "secret-123" not in payload["detail"]
    assert "secret-123" not in payload["command"]
```

- [x] **步骤 2：运行密码型 SSH 测试，确认当前实现失败**

运行：

```bash
pytest tests/test_exec_ssh_password.py -v
```

预期：

- 由于 `ssh_password` 尚未被接受而失败
- 或由于审计日志仍泄漏原始密码值而失败

- [x] **步骤 3：为 `exec` 增加最小可用的密码支持**

实现要求：

- 在 `ExecTool.execute()` 中增加可选参数 `ssh_password`
- 只通过进程内存把密码传给远程传输层
- 绝不把密码拼接进 shell 命令字符串
- 绝不在返回文本中包含密码
- 绝不在审计日志的 `command` / `detail` 中包含密码

建议采用的最小机制：

- 传输辅助逻辑接收 `ssh_password`
- 辅助逻辑通过环境变量或标准输入传递密码
- 审计日志只记录 `target`、命令和脱敏后的元数据

这一阶段不要实现：

- timeout / lease 系统
- 显式的密码清理命令
- 持久化凭据存储

- [x] **步骤 4：补充持久化安全回归测试**

扩展 `tests/test_loop_save_turn.py`，或在邻近测试中增加覆盖，确保带有敏感信息的运行时字段不会写入保存后的会话历史。

断言方向示例：

```python
assert "secret-123" not in saved_jsonl_text
```

- [x] **步骤 5：重新运行密码与持久化相关测试**

运行：

```bash
pytest tests/test_exec_ssh_password.py tests/test_loop_save_turn.py -v
```

预期：

- 测试通过
- 密码不会泄漏到审计日志或会话持久化内容中

- [x] **步骤 6：运行完整的 `exec` 相关测试集**

运行：

```bash
pytest tests/test_exec_*.py tests/test_loop_save_turn.py tests/test_commands.py -v
```

预期：

- 测试通过
- 现有 `exec` 审批与 guard 行为没有回归

- [x] **步骤 7：提交本阶段改动**

```bash
git add nanobot/agent/tools/shell.py nanobot/agent/tools/exec_transport.py tests/test_exec_ssh_password.py tests/test_loop_save_turn.py tests/test_commands.py
git commit -m "feat: add password-backed ssh execution to exec"
```

## 阶段 4：基线文档更新与端到端验证

### 任务 4：从用户入口视角补充文档并验证第一阶段行为

**涉及文件：**
- 修改：`README.md`
- 修改：`docs/superpowers/specs/2026-03-15-shell-first-ssh-first-troubleshooting-agent-design.md`（仅当实现与设计有偏差时）
- 测试：`tests/test_commands.py`

- [x] **步骤 1：补齐会失败或缺失的 CLI / 配置回归测试**

补充或扩展测试，验证以下内容：

- `ExecTool` 可以接受 `target`
- 配置序列化与反序列化能正确保留新增的 `exec` / SSH 设置
- 如果 CLI 或默认配置会暴露帮助文本，则这些帮助文本仍然连贯

- [x] **步骤 2：运行聚焦的命令与配置测试**

运行：

```bash
pytest tests/test_commands.py -v
```

预期：

- 如果新增配置或行为还未写入文档、或尚未接入测试，这里应先失败

- [x] **步骤 3：以最小范围更新面向用户的文档**

只记录第一阶段已经落地的行为：

- `exec` 现在支持 `target`
- 远程 SSH 由内部处理，而不是要求模型自己构造 `ssh ...`
- 密码型 SSH 只在进程内存中使用，不做持久化

不要记录尚未实现的后续调查动作能力。

- [x] **步骤 4：基于当前 worktree 的干净基线运行全量测试**

运行：

```bash
pytest
```

预期：

- 测试通过
- 相比该 worktree 已建立的干净基线没有出现回归

- [x] **步骤 5：提交本阶段改动**

```bash
git add README.md tests/test_commands.py
git commit -m "docs: describe target-aware exec phase 1 behavior"
```

## 计划审查说明

当前执行环境没有暴露专门的 subagent / 任务审查工具，因此每个阶段都需要人工对照以下内容完成审查：

- `/Users/ruibinhuang/.codex/superpowers/skills/writing-plans/plan-document-reviewer-prompt.md`
- 设计文档：`docs/superpowers/specs/2026-03-15-shell-first-ssh-first-troubleshooting-agent-design.md`

每个阶段的人工审查清单：

- 没有 TODO 或占位文本
- 范围始终停留在第一阶段
- 任务粒度原子化，且可直接执行
- 每个任务都包含失败测试、验证命令和提交动作
- 文件职责保持清晰

## 执行交接

计划已保存到 `docs/superpowers/plans/2026-03-15-target-aware-exec-phase1.md`。可以进入实现阶段。
