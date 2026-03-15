# Repository Guidelines

## Project Structure & Module Organization
- `nanobot/`: 核心包，包含 `agent loop`、tools、policies、channels、config、skills、templates。
- `tests/`: pytest 单元/集成测试。
- `docs/`: PRD、实现计划、设计参考与运行文档。
- `scripts/`: 本地 lab 与 acceptance 脚本，例如 `scripts/local_ssh_lab.py`。
- `examples/`: 示例配置与案例。
- `assets/`: logo/静态资源；`case/` 存放样例场景。

## Build, Test, and Development Commands
- `pip install -e .`: 本地可编辑安装 CLI。
- `pip install -e ".[dev]"`: 安装开发依赖（测试、lint）。
- `nanobot onboard`: 生成 `~/.nanobot/workspace` 模板。
- `nanobot agent`: 本地排障代理运行入口。
- `nanobot gateway`: IM 网关（Telegram/Mattermost）。
- `python3 -m pytest`: 全量测试。
- `python3 -m pytest tests/test_commands.py -v`: 运行聚焦回归。

## Coding Style & Naming Conventions
- Python 3.11+，4 空格缩进。
- `ruff` 负责 lint；行宽 100（见 `pyproject.toml`）。
- 函数/变量用 `snake_case`，类用 `CamelCase`。
- Tool 名称保持稳定、对外可读（如 `exec`, `diagnose_log_read`）。

## Testing Guidelines
- 测试框架：`pytest` + `pytest-asyncio`。
- 文件命名 `tests/test_*.py`；异步测试加 `@pytest.mark.asyncio`。
- 行为测试优先覆盖 tools/policies；需要 E2E 时放在 `scripts/` 并保留最小 acceptance。

## Architecture Overview
- 入口以 `AgentLoop` 驱动工具调用，排障优先走调查类 tools，再回退到自由 `exec`。
- 远程目标使用 `target="user@host[:port]"`；本机使用 `target="local"`。
- SSH 回环验证可用 `scripts/local_ssh_lab.py` 与 `scripts/run_exec_ssh_loopback_acceptance.py`。
- 规划与里程碑记录在 `docs/superpowers/plans/`，合并前请同步勾选进度。
- 常用配置字段：`tools.troubleshooting`、`tools.exec`、`providers.*`、`workspace.*`。

## Runbook Notes
- 常用只读调查：`find_logs`, `read_log_tail`, `search_log`, `service_status`, `process_snapshot`。
- 高风险命令需要显式审批，参考 `~/.nanobot/workspace/approvals/exec_allow.json`。
- 报告输出默认在 `~/.nanobot/workspace/reports/inspection`（详见 README）。

## Commit & Pull Request Guidelines
- 使用仓库已有前缀：`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`。
- PR 描述包含：变更摘要、影响范围、测试命令、关联 issue。
- 仅当 UI/文档渲染变化时提交截图。

## Security & Configuration Tips
- 配置文件：`~/.nanobot/config.json`。
- 工作区：`~/.nanobot/workspace`（audit 日志默认在 `audit/commands.jsonl`）。
- 避免提交密钥/真实凭据；测试数据需脱敏。
