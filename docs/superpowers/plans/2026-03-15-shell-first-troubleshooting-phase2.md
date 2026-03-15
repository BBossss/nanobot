# Shell-First Troubleshooting Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 `exec(target=...)`、SSH 内部执行模式和轻量调查收敛能力之上，补齐高频只读调查动作与模板化连续调查路径，让 agent 在单机本地/远程排障场景下达到“中等可用”。

**Architecture:** 本阶段不新增独立 SSH tool，不引入重型 planner，也不补超时租约之类治理系统。实现方式是在现有 `exec` 之上增加一组 target-aware 的只读排障动作工具，并在 `AgentLoop`、`ContextBuilder`、HCI skills 中补轻量调查模板和去重/收敛提示，让模型优先走稳定动作，必要时再回退到自由 `exec`。

**Tech Stack:** Python 3.11+、Pydantic、asyncio subprocess、pytest、pytest-asyncio、Markdown skills

---

## 范围决策

这份计划只覆盖已经明确的下一阶段能力：

- 高频只读调查动作
- 排障 skill / system prompt 的模板化调查路径
- `AgentLoop` 的轻量连续调查增强

明确不放进本计划的内容：

- 独立 SSH tool
- 凭据治理平台
- timeout / lease / secret cleanup 子系统
- 多主机编排
- 重型 planner / case 重构
- 生产级强安全治理

## 文件结构

### 需要新增的文件

- `nanobot/agent/tools/troubleshooting.py`
  - 新增高频只读调查动作工具
  - 第一批动作放在同一文件中，避免一开始就过度拆分
  - 统一接受 `target`
- `tests/test_troubleshooting_tools.py`
  - 覆盖调查动作的参数、只读行为、输出边界、远程分流
- `tests/test_agentloop_troubleshooting_flow.py`
  - 覆盖“优先调查动作、重复采样抑制、自由 exec 兜底”的连续调查链路

### 需要修改的现有文件

- `nanobot/config/schema.py`
  - 增加排障动作工具配置
  - 声明默认日志根目录、tail/search 上限、recent files 上限等
- `nanobot/agent/tools/exec_transport.py`
  - 继续承载 target 解析与 SSH 命令封装
  - 补最小的 target label / remote argv 复用辅助函数，供调查动作工具调用
- `nanobot/agent/tools/shell.py`
  - 保持自由 `exec` 作为兜底路径
  - 复用 transport/helper，避免自由 `exec` 与调查动作出现两套 target 解析
- `nanobot/agent/tools/diagnostics.py`
  - 保留当前受限 diagnostics 工具
  - 视实现需要抽取共享的只读命令执行辅助，避免和新工具重复拼 subprocess
- `nanobot/agent/loop.py`
  - 在现有轮数上限/重复结果复用基础上，增加对象级调查状态与工具优先级提示
- `nanobot/agent/context.py`
  - 在 system prompt 中明确“先调查动作、后自由 exec”的优先级
  - 补充 target-aware 排障提示
- `nanobot/skills/hci-troubleshooting/SKILL.md`
  - 增加高频调查模板和优先检查顺序
- `nanobot/skills/hci-troubleshooting/references/service-log-map.md`
  - 只补当前模板真正会引用的日志入口，不做大而全扩展
- `tests/test_diagnostics_tool.py`
  - 补共享 helper 或兼容性回归
- `tests/test_agentloop_investigation.py`
  - 扩展 investigation state 断言
- `tests/test_hci_skill_content.py`
  - 回归新的调查模板、tool 优先级、远程规则
- `tests/test_commands.py`
  - 如果新增配置字段，补配置序列化和 CLI 装配回归

## 实现原则

- 优先做高频排障路径，不先做完整工具平台
- 调查动作要尽量稳定、规范化，但始终保留自由 `exec` 兜底
- 所有远程排障仍统一走 `target`
- 先补最常见单机问题的可用性，再补长尾能力
- 每个任务都按 TDD 执行，先写失败测试，再补最小实现

## Chunk 1: 调查动作工具底座

### Task 1: 增加排障动作工具配置与注册

**Files:**
- Create: `tests/test_troubleshooting_tools.py`
- Modify: `nanobot/config/schema.py`
- Modify: `nanobot/agent/loop.py`
- Modify: `nanobot/cli/commands.py`
- Test: `tests/test_troubleshooting_tools.py`
- Test: `tests/test_commands.py`

- [x] **Step 1: 先写失败测试，定义排障动作配置默认值与工具注册结果**

```python
from unittest.mock import MagicMock

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import TroubleshootingToolConfig


def test_troubleshooting_tool_config_defaults() -> None:
    cfg = TroubleshootingToolConfig()

    assert cfg.enabled is True
    assert "/sf/log" in cfg.allowed_log_roots
    assert cfg.default_tail_lines == 200
    assert cfg.max_recent_files == 50


def test_agent_loop_registers_troubleshooting_tools(tmp_path) -> None:
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="test-model",
    )

    assert loop.tools.get("find_logs") is not None
    assert loop.tools.get("read_log_tail") is not None
    assert loop.tools.get("service_status") is not None
```

- [x] **Step 2: 运行聚焦测试，确认当前缺少配置模型和工具注册**

Run: `python3 -m pytest tests/test_troubleshooting_tools.py tests/test_commands.py -v`

Expected:
- `TroubleshootingToolConfig` 不存在
- `find_logs` / `read_log_tail` / `service_status` 尚未注册

- [x] **Step 3: 在配置层补齐排障动作配置模型**

在 `nanobot/config/schema.py` 中新增：

```python
class TroubleshootingToolConfig(Base):
    enabled: bool = True
    timeout: int = 20
    allowed_log_roots: list[str] = Field(default_factory=lambda: ["/var/log", "/opt/logs", "/sf/log"])
    default_tail_lines: int = 200
    max_tail_lines: int = 2000
    max_search_hits: int = 100
    max_recent_files: int = 50
```

并在 `ToolsConfig` 中挂入：

```python
troubleshooting: TroubleshootingToolConfig = Field(default_factory=TroubleshootingToolConfig)
```

- [x] **Step 4: 在 `AgentLoop` 中注册排障动作工具占位实现**

先只要求工具可发现，不要求动作已完整实现。为了避免新参数侵入现有代码路径，
建议在 `AgentLoop` 中新增 `troubleshooting_config` 参数，并在 CLI 里传入 `config.tools.troubleshooting`：

```python
if self.troubleshooting_config is None or self.troubleshooting_config.enabled:
    self.tools.register(FindLogsTool(...))
    self.tools.register(ReadLogTailTool(...))
    self.tools.register(SearchLogTool(...))
    self.tools.register(ServiceStatusTool(...))
    self.tools.register(ProcessSnapshotTool(...))
```

- [x] **Step 5: 回跑聚焦测试与现有配置回归**

Run: `python3 -m pytest tests/test_troubleshooting_tools.py tests/test_commands.py tests/test_tool_validation.py -v`

Expected:
- 配置默认值测试通过
- 工具注册测试通过
- 现有配置回归不失败

- [x] **Step 6: 提交本任务**

```bash
git add nanobot/config/schema.py nanobot/agent/loop.py tests/test_troubleshooting_tools.py tests/test_commands.py
git commit -m "feat: add troubleshooting tool config skeleton"
```

### Task 2: 抽出 target-aware 的只读调查动作运行底座

**Files:**
- Create: `nanobot/agent/tools/troubleshooting.py`
- Modify: `nanobot/agent/tools/exec_transport.py`
- Modify: `nanobot/agent/tools/shell.py`
- Modify: `nanobot/agent/tools/diagnostics.py`
- Test: `tests/test_troubleshooting_tools.py`
- Test: `tests/test_diagnostics_tool.py`
- Test: `tests/test_exec_target_aware.py`

- [x] **Step 1: 写失败测试，固定本地/远程 target 分流和原始 SSH 拦截复用**

```python
import pytest

from nanobot.agent.tools.troubleshooting import _build_target_runner


def test_target_runner_parses_local_and_remote_targets() -> None:
    runner = _build_target_runner(default_target="local", ssh_enabled=True)

    assert runner.parse_target("local").kind == "local"
    assert runner.parse_target("ops@host-a:2222").host == "host-a"


@pytest.mark.asyncio
async def test_target_runner_rejects_raw_ssh_command(monkeypatch) -> None:
    runner = _build_target_runner(default_target="local", ssh_enabled=True)

    result = await runner.run(command="ssh root@host-a uptime", target="local")

    assert "Use target=" in result
```

- [x] **Step 2: 运行失败测试，确认新 helper 尚不存在**

Run: `python3 -m pytest tests/test_troubleshooting_tools.py::test_target_runner_parses_local_and_remote_targets tests/test_troubleshooting_tools.py::test_target_runner_rejects_raw_ssh_command -v`

Expected:
- `nanobot.agent.tools.troubleshooting` 缺失
- 或 target runner 相关属性缺失

- [x] **Step 3: 在 `troubleshooting.py` 中实现共享 target runner，在 `shell.py` 中改为复用它**

共享 runner 至少应支持：

```python
class TargetCommandRunner:
    def parse_target(self, target: str | None) -> ExecTarget: ...
    async def run(self, command: str, target: str | None, env: dict[str, str] | None = None) -> tuple[str, str]: ...
```

约束：

- 统一使用 `parse_exec_target()`
- 统一复用 `build_ssh_command()`
- 本地 `target` 下统一拒绝原始 `ssh ...`
- 保持 `ExecTool` 当前密码 SSH 行为不回退

- [x] **Step 4: 在 diagnostics 工具中只抽共享执行辅助，不修改对外行为**

目标是避免后续 `service_status` / `process_snapshot` 再重复维护 subprocess 逻辑。  
如果 `diagnostics.py` 不适合抽 helper，就只在 `troubleshooting.py` 内部提供私有 helper，并补兼容测试。

- [x] **Step 5: 跑共享底座相关测试**

Run: `python3 -m pytest tests/test_troubleshooting_tools.py tests/test_diagnostics_tool.py tests/test_exec_target_aware.py -v`

Expected:
- 新的 target runner 行为通过
- 现有 `exec` target-aware 回归不失败
- 现有 diagnostics 回归不失败

- [x] **Step 6: 提交本任务**

```bash
git add nanobot/agent/tools/troubleshooting.py nanobot/agent/tools/exec_transport.py nanobot/agent/tools/shell.py nanobot/agent/tools/diagnostics.py tests/test_troubleshooting_tools.py tests/test_diagnostics_tool.py tests/test_exec_target_aware.py
git commit -m "refactor: share target-aware readonly command runner"
```

## Chunk 2: 高频调查动作

### Task 3: 实现日志入口调查动作

**Files:**
- Modify: `nanobot/agent/tools/troubleshooting.py`
- Modify: `nanobot/agent/loop.py`
- Test: `tests/test_troubleshooting_tools.py`
- Test: `tests/test_hci_skill_content.py`

- [x] **Step 1: 先写失败测试，固定 `find_logs` / `read_log_tail` / `search_log` 的输入输出**

```python
import pytest

from nanobot.agent.tools.troubleshooting import FindLogsTool, ReadLogTailTool, SearchLogTool


@pytest.mark.asyncio
async def test_find_logs_returns_bounded_matches(tmp_path) -> None:
    tool = FindLogsTool(allowed_log_roots=[str(tmp_path)])
    (tmp_path / "today").mkdir()
    (tmp_path / "today" / "upgrade-server.log").write_text("ok\n", encoding="utf-8")

    result = await tool.execute(keyword="upgrade", target="local")

    assert "upgrade-server.log" in result


@pytest.mark.asyncio
async def test_read_log_tail_supports_remote_target(monkeypatch) -> None:
    tool = ReadLogTailTool(...)
    monkeypatch.setattr(tool, "_run_tail", AsyncMock(return_value=("tail output", "ok")))

    result = await tool.execute(path="/sf/log/today/update.log", target="ops@host-a")

    assert "tail output" in result
```

- [x] **Step 2: 跑失败测试，确认工具尚未实现**

Run: `python3 -m pytest tests/test_troubleshooting_tools.py -k "find_logs or read_log_tail or search_log" -v`

Expected:
- 工具类不存在
- 或参数/返回值与预期不符

- [x] **Step 3: 在 `troubleshooting.py` 中实现日志调查动作**

最小动作集：

- `find_logs(keyword, target="local", limit=20)`
- `read_log_tail(path, target="local", lines=200)`
- `search_log(path, pattern, target="local", max_hits=50, ignore_case=True)`

实现约束：

- 本地日志可以直接读文件或调用受控命令
- 远程日志统一走 target runner + 只读 shell 命令
- 输出统一带上目标机和文件路径
- 超出上限时明确提示已截断

- [x] **Step 4: 在 `AgentLoop` 中注册这三个工具的真实实现**

要求：

- 不移除原有 `diagnose_log_read` / `diagnose_log_search`
- 保持新动作作为 HCI 排障主路径
- 现有工具仍可作为补充能力保留

- [x] **Step 5: 运行聚焦测试与 skill 内容回归**

Run: `python3 -m pytest tests/test_troubleshooting_tools.py tests/test_hci_skill_content.py -v`

Expected:
- 日志调查动作测试通过
- HCI skill 若引用了新 tool 名称，则对应断言通过

- [x] **Step 6: 提交本任务**

```bash
git add nanobot/agent/tools/troubleshooting.py nanobot/agent/loop.py tests/test_troubleshooting_tools.py tests/test_hci_skill_content.py
git commit -m "feat: add target-aware log investigation tools"
```

### Task 4: 实现服务与进程调查动作

**Files:**
- Modify: `nanobot/agent/tools/troubleshooting.py`
- Modify: `nanobot/skills/hci-troubleshooting/SKILL.md`
- Test: `tests/test_troubleshooting_tools.py`
- Test: `tests/test_hci_skill_content.py`

- [x] **Step 1: 先写失败测试，固定 `service_status` / `process_snapshot` 的行为**

```python
import pytest

from nanobot.agent.tools.troubleshooting import ProcessSnapshotTool, ServiceStatusTool


@pytest.mark.asyncio
async def test_service_status_checks_systemd_first(monkeypatch) -> None:
    tool = ServiceStatusTool(...)
    monkeypatch.setattr(tool, "_run_status", AsyncMock(return_value=("active (running)", "ok")))

    result = await tool.execute(service="nginx", target="ops@host-a")

    assert "nginx" in result
    assert "ops@host-a" in result


@pytest.mark.asyncio
async def test_process_snapshot_returns_bounded_top_processes(monkeypatch) -> None:
    tool = ProcessSnapshotTool(...)
    monkeypatch.setattr(tool, "_run_snapshot", AsyncMock(return_value=("proc list", "ok")))

    result = await tool.execute(target="local")

    assert "proc list" in result
```

- [x] **Step 2: 运行失败测试**

Run: `python3 -m pytest tests/test_troubleshooting_tools.py -k "service_status or process_snapshot" -v`

Expected:
- 工具尚未实现
- 或当前返回格式不含 target / service 元数据

- [x] **Step 3: 实现两个高频状态动作**

动作定义：

- `service_status(service, target="local")`
  - 优先 `systemctl status --no-pager <service>`
  - 如命令不存在或失败，再回退到 `ps` / `pgrep` 风格检查
- `process_snapshot(target="local", limit=20)`
  - 固定使用只读进程视图
  - 输出顶部 CPU / MEM 占用信息

返回格式最小要求：

```text
[target=ops@host-a] service_status(nginx)
...
```

- [x] **Step 4: 更新 HCI skill，写入服务状态与日志联合排查模板**

新增原则：

- 先服务状态，再日志入口
- 服务已异常时优先采最近错误与进程存活
- 不把“服务 active”直接当作问题已排除

- [x] **Step 5: 回跑测试**

Run: `python3 -m pytest tests/test_troubleshooting_tools.py tests/test_hci_skill_content.py tests/test_hci_skills.py -v`

Expected:
- 新工具行为通过
- skill 文案与 discoverability 回归通过

- [x] **Step 6: 提交本任务**

```bash
git add nanobot/agent/tools/troubleshooting.py nanobot/skills/hci-troubleshooting/SKILL.md tests/test_troubleshooting_tools.py tests/test_hci_skill_content.py tests/test_hci_skills.py
git commit -m "feat: add service and process investigation tools"
```

### Task 5: 实现 P1 调查动作并补齐 SOP 模板

**Files:**
- Modify: `nanobot/agent/tools/troubleshooting.py`
- Modify: `nanobot/skills/hci-troubleshooting/SKILL.md`
- Modify: `nanobot/skills/hci-storage-network-sop/SKILL.md`
- Test: `tests/test_troubleshooting_tools.py`
- Test: `tests/test_hci_skill_content.py`

- [x] **Step 1: 写失败测试，固定 P1 动作最小可用行为**

```python
@pytest.mark.asyncio
async def test_journal_tail_accepts_service_and_target(monkeypatch) -> None:
    tool = JournalTailTool(...)
    monkeypatch.setattr(tool, "_run_journal", AsyncMock(return_value=("journal lines", "ok")))

    result = await tool.execute(service="nginx", target="ops@host-a", lines=100)

    assert "journal lines" in result


@pytest.mark.asyncio
async def test_network_snapshot_returns_bounded_output(monkeypatch) -> None:
    tool = NetworkSnapshotTool(...)
    monkeypatch.setattr(tool, "_run_snapshot", AsyncMock(return_value=("network", "ok")))

    result = await tool.execute(target="local")

    assert "network" in result
```

- [x] **Step 2: 跑失败测试**

Run: `python3 -m pytest tests/test_troubleshooting_tools.py -k "journal_tail or disk_snapshot or network_snapshot or find_recent_files" -v`

Expected:
- P1 工具不存在

- [x] **Step 3: 在 `troubleshooting.py` 中补齐 P1 动作**

动作范围：

- `journal_tail(service, target="local", lines=200)`
- `disk_snapshot(target="local")`
- `network_snapshot(target="local")`
- `find_recent_files(base_path, target="local", minutes=60, limit=20)`

实现要求：

- 仍然只读
- 远程统一走 target runner
- 输出简洁、带 target 元数据
- 命令失败时返回可继续扩查的错误信息

- [x] **Step 4: 在 HCI skill / SOP 中补调查模板**

至少增加以下模板：

- 服务异常模板：`service_status -> journal_tail -> read_log_tail`
- 磁盘异常模板：`disk_snapshot -> find_recent_files -> search_log`
- 网络异常模板：`network_snapshot -> process_snapshot -> search_log`

- [x] **Step 5: 运行动作与 skill 回归**

Run: `python3 -m pytest tests/test_troubleshooting_tools.py tests/test_hci_skill_content.py tests/test_hci_skills.py -v`

Expected:
- P1 动作通过
- skill 文案明确出现上述模板和远程规则

- [x] **Step 6: 提交本任务**

```bash
git add nanobot/agent/tools/troubleshooting.py nanobot/skills/hci-troubleshooting/SKILL.md nanobot/skills/hci-storage-network-sop/SKILL.md tests/test_troubleshooting_tools.py tests/test_hci_skill_content.py tests/test_hci_skills.py
git commit -m "feat: add secondary troubleshooting investigation tools"
```

## Chunk 3: 连续调查轻增强

### Task 6: 为 `AgentLoop` 增加对象级调查状态与更稳的收敛信号

**Files:**
- Modify: `nanobot/agent/loop.py`
- Modify: `tests/test_agentloop_investigation.py`
- Create: `tests/test_agentloop_troubleshooting_flow.py`

- [x] **Step 1: 先写失败测试，固定对象级重复调查与主路径优先行为**

```python
from nanobot.providers.base import LLMResponse, ToolCallRequest


@pytest.mark.asyncio
async def test_agent_loop_marks_repeated_log_sampling_as_stale(tmp_path) -> None:
    loop = _make_loop(tmp_path, max_rounds=8)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(content="", tool_calls=[ToolCallRequest(id="1", name="read_log_tail", arguments={"path": "/sf/log/today/a.log", "target": "host-a"})]),
            LLMResponse(content="", tool_calls=[ToolCallRequest(id="2", name="read_log_tail", arguments={"path": "/sf/log/today/a.log", "target": "host-a"})]),
            LLMResponse(content="done", tool_calls=[]),
        ]
    )
    loop.tools.execute = AsyncMock(return_value="[target=host-a] same tail")

    final_content, _, messages = await loop._run_agent_loop([...])

    assert any("no new evidence" in str(m.get("content", "")).lower() for m in messages if m.get("role") == "tool")
```

- [x] **Step 2: 运行失败测试，确认当前只有泛化结果缓存**

Run: `python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -v`

Expected:
- 新场景测试失败
- 或缺少调查流测试文件

- [x] **Step 3: 扩展 `InvestigationState` 与循环内判定**

最小新增状态：

```python
@dataclass
class InvestigationState:
    rounds: int = 0
    consecutive_stale_rounds: int = 0
    checked_objects: set[str] = field(default_factory=set)
    checked_directions: set[str] = field(default_factory=set)
```

目标行为：

- 对同一 `tool + target + object` 的重复采样直接视为 stale
- 对“同一方向无新证据”的连续扩查更早收敛
- 仍保留现有 `max_investigation_rounds`

- [x] **Step 4: 增加一条“优先使用调查动作，必要时再用 exec”的 loop 提示**

实现位置可选：

- `loop.py` 在达到工具轮次时插入隐式提示
- 或 `context.py` 常驻说明

优先选择改动更小、测试更稳的一种，不要两边都做重逻辑。

- [x] **Step 5: 跑 investigation 回归**

Run: `python3 -m pytest tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py -v`

Expected:
- 原有轮数上限 / stale 逻辑继续通过
- 新增对象级重复调查测试通过

- [x] **Step 6: 提交本任务**

```bash
git add nanobot/agent/loop.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py
git commit -m "feat: improve troubleshooting investigation convergence"
```

### Task 7: 调整 system prompt 和 HCI skill，让模型更少自由发挥

**Files:**
- Modify: `nanobot/agent/context.py`
- Modify: `nanobot/skills/hci-troubleshooting/SKILL.md`
- Modify: `tests/test_context_prompt_cache.py`
- Modify: `tests/test_hci_skill_content.py`

- [x] **Step 1: 写失败测试，固定 prompt 中的新约束**

```python
from nanobot.agent.context import ContextBuilder


def test_context_mentions_troubleshooting_tool_priority(tmp_path) -> None:
    builder = ContextBuilder(tmp_path)

    prompt = builder.build_system_prompt()

    assert "优先使用高频只读调查动作" in prompt
    assert "必要时再回退到自由 `exec`" in prompt
```

- [x] **Step 2: 运行失败测试**

Run: `python3 -m pytest tests/test_context_prompt_cache.py tests/test_hci_skill_content.py -v`

Expected:
- 新提示断言失败

- [x] **Step 3: 在 `context.py` 与 HCI skill 中补固定调查顺序**

最小要求：

- 先确认目标机、时间窗口、服务/日志入口
- 优先使用 `find_logs` / `read_log_tail` / `search_log` / `service_status`
- 自由 `exec` 仅用于：
  - 调查动作覆盖不到的只读采样
  - 需要临时组合命令时的兜底

- [x] **Step 4: 回跑 prompt / skill 回归**

Run: `python3 -m pytest tests/test_context_prompt_cache.py tests/test_hci_skill_content.py tests/test_hci_skills.py -v`

Expected:
- prompt 与 skill 文案断言通过
- 现有 skill discoverability 不回退

- [x] **Step 5: 提交本任务**

```bash
git add nanobot/agent/context.py nanobot/skills/hci-troubleshooting/SKILL.md tests/test_context_prompt_cache.py tests/test_hci_skill_content.py tests/test_hci_skills.py
git commit -m "feat: guide troubleshooting flow toward investigation tools first"
```

## Chunk 4: 验证与收口

### Task 8: 做一轮聚焦回归与本机 acceptance

**Files:**
- Modify: `tests/test_exec_loopback_acceptance.py`
- Modify: `tests/test_exec_ssh_password.py`
- Modify: `tests/test_local_ssh_lab.py`
- Modify: `scripts/run_exec_ssh_loopback_acceptance.py`

- [x] **Step 1: 补一条调查动作走远程 target 的 acceptance 场景**

建议用例：

- loopback SSH 到 `127.0.0.1`
- 调用 `service_status(target="127.0.0.1", service="sshd")` 或等价本机服务
- 调用 `read_log_tail(target="127.0.0.1", path="...")` 的最小验证路径

- [x] **Step 2: 跑单元测试**

Run: `python3 -m pytest tests/test_troubleshooting_tools.py tests/test_agentloop_investigation.py tests/test_agentloop_troubleshooting_flow.py tests/test_context_prompt_cache.py tests/test_hci_skill_content.py tests/test_hci_skills.py -v`

Expected:
- 新增工具、调查链路、skill/prompt 回归通过

- [x] **Step 3: 跑已有 SSH 回环与 acceptance**

Run: `python3 scripts/local_ssh_lab.py start`

Expected:
- 启动本机 loopback SSH lab 成功

Run: `python3 scripts/run_exec_ssh_loopback_acceptance.py`

Expected:
- 现有公钥/密码 SSH acceptance 继续通过

- [x] **Step 4: 如果本阶段扩展了 acceptance 脚本，就运行新增场景**

Run: `python3 -m pytest tests/test_exec_loopback_acceptance.py tests/test_exec_ssh_password.py tests/test_local_ssh_lab.py -v`

Expected:
- 新增调查动作远程场景通过
- 现有 SSH 密码与 loopback 能力不回退

- [x] **Step 5: 提交最终收口**

```bash
git add tests/test_troubleshooting_tools.py tests/test_agentloop_troubleshooting_flow.py tests/test_exec_loopback_acceptance.py tests/test_exec_ssh_password.py tests/test_local_ssh_lab.py scripts/run_exec_ssh_loopback_acceptance.py
git commit -m "test: cover troubleshooting investigation acceptance"
```

## 实施顺序建议

建议严格按下面顺序执行：

1. 先补配置与工具注册骨架
2. 再抽共享 target-aware 运行底座
3. 先做 P0 动作，再做 P1 动作
4. 最后补 loop / prompt / skill 的轻增强
5. 收尾时统一做 loopback acceptance

这样可以保证：

- 任一中间状态都可测试
- 远程 target 行为始终围绕 `exec(target=...)` 既有设计
- 不会为了“让模型更聪明”而先把系统做复杂

## 风险与取舍

- 新调查动作会和现有 `diagnose_*` 存在一定功能重叠，这是可接受的；当前目标是更稳的排障主路径，不是立即统一工具谱系。
- 如果共享 target runner 抽象过重，会拖慢交付；实现时优先抽最小公用部分。
- `service_status`、`journal_tail` 等命令在不同环境存在差异，测试要优先 mock 分流与返回格式，再做少量 acceptance。
- 本阶段的成功标准是“明显更会查、少空转、覆盖更多只读排障场景”，不是“一次性自动定位全部根因”。

Plan complete and saved to `docs/superpowers/plans/2026-03-15-shell-first-troubleshooting-phase2.md`. Ready to execute?
