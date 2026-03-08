<div align="center">
  <img src="nanobot_logo.png" alt="HCIGuard" width="420">
  <h1>HCIGuard</h1>
  <p>HCI troubleshooting assistant built on top of nanobot.</p>
  <p>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
</div>

HCIGuard is a focused troubleshooting assistant for HCI environments. It keeps the original nanobot runtime as the base, then adds HCI-oriented diagnostics, case recording, inspection workflows, safety controls, and IM integration for operational use.

## What It Does

- Read logs and inspect host state with controlled, read-only diagnostic tools
- Record troubleshooting sessions as searchable cases
- Run inspections, generate reports, and optionally convert findings into cases
- Enforce readonly command execution with manual approvals and audit logging
- Support multiple model providers
- Deliver through CLI, Telegram, and Mattermost

## Current Scope

Current interaction entry points:

- CLI
- Telegram
- Mattermost

Current HCI-oriented capabilities:

- Diagnostics: `diagnose_log_read`, `diagnose_log_search`, `diagnose_system_status`
- Cases: record, import, search, show
- Inspection: log scan, command/journal targets, report output, scheduled execution
- Safety: readonly `exec`, approval file, unified command audit
- Planning: structured troubleshooting plans
- Skills: built-in HCI troubleshooting skills

## Architecture

Main runtime flow:

`CLI / Telegram / Mattermost -> MessageBus -> AgentLoop -> Tools / LLM -> Response`

Core HCI additions in this fork:

- Diagnostics tools: [diagnostics.py](/Users/ruibinhuang/repos/nanobot/nanobot/agent/tools/diagnostics.py)
- Case system: [store.py](/Users/ruibinhuang/repos/nanobot/nanobot/cases/store.py)
- Inspection service: [service.py](/Users/ruibinhuang/repos/nanobot/nanobot/inspection/service.py)
- Command safety and audit: [command_guard.py](/Users/ruibinhuang/repos/nanobot/nanobot/security/command_guard.py), [audit.py](/Users/ruibinhuang/repos/nanobot/nanobot/security/audit.py)
- Mattermost channel: [mattermost.py](/Users/ruibinhuang/repos/nanobot/nanobot/channels/mattermost.py)

## Install

From source:

```bash
git clone https://github.com/BBossss/nanobot.git
cd nanobot
pip install -e .
```

## Quick Start

Initialize:

```bash
nanobot onboard
```

Configure your model in `~/.nanobot/config.json`:

```json
{
  "agents": {
    "defaults": {
      "model": "openai-codex/gpt-5.1-codex-max",
      "provider": "auto"
    }
  },
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  }
}
```

Start local interactive mode:

```bash
nanobot agent
```

Start gateway mode:

```bash
nanobot gateway
```

## Minimal HCI Configuration

Example:

```json
{
  "cases": {
    "enabled": true,
    "autoRecord": true,
    "recordMode": "end_only",
    "path": "~/.nanobot/workspace/notes/cases"
  },
  "inspection": {
    "enabled": true,
    "reportDir": "~/.nanobot/workspace/reports/inspection",
    "generateCaseOn": "error",
    "targets": [
      {
        "name": "syslog",
        "kind": "log_file",
        "enabled": true,
        "path": "/var/log/system.log",
        "keywords": ["error", "failed", "panic"],
        "maxLines": 500,
        "maxMatches": 50
      }
    ]
  },
  "tools": {
    "exec": {
      "readonlyMode": true,
      "allowedCommands": ["ls", "cat", "grep", "journalctl", "systemctl"],
      "approvalFile": "~/.nanobot/workspace/approvals/exec_allow.json"
    },
    "diagnostics": {
      "enabled": true,
      "timeout": 20,
      "maxReadLines": 2000,
      "maxSearchHits": 100,
      "allowedPaths": ["/var/log", "/opt/logs"]
    }
  }
}
```

A reference file is also available at [hci-minimal-config.json](/Users/ruibinhuang/repos/nanobot/examples/hci-minimal-config.json).

## Channels

### Telegram

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

### Mattermost

```json
{
  "channels": {
    "mattermost": {
      "enabled": true,
      "baseUrl": "https://mm.example.com",
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

## Common Commands

```bash
nanobot status
nanobot agent
nanobot gateway
nanobot cases list --limit 20
nanobot cases show INC-YYYYMMDD-001
nanobot cases import ./legacy_cases
nanobot inspection run --no-llm --trigger manual
nanobot approvals list
nanobot approvals grant --command "systemctl restart kubelet"
nanobot approvals revoke --command "systemctl restart kubelet"
```

## Testing

Run the current focused regression set:

```bash
python3 -m pytest -q \
  tests/test_commands.py \
  tests/test_mattermost_channel.py \
  tests/test_case_policy.py \
  tests/test_case_record_mode.py \
  tests/test_cases.py \
  tests/test_inspection_service.py \
  tests/test_exec_readonly_approval.py \
  tests/test_cron_inspection_tool.py \
  tests/test_hci_skills.py
```

Live validation assets:

- [hci-live-validation-checklist-v1.md](/Users/ruibinhuang/repos/nanobot/docs/hci-live-validation-checklist-v1.md)
- [run_hci_acceptance.sh](/Users/ruibinhuang/repos/nanobot/scripts/run_hci_acceptance.sh)

## Documentation

- [HCIGuard feature guide](/Users/ruibinhuang/repos/nanobot/docs/hci-feature-guide-v1.md)
- [Technical design](/Users/ruibinhuang/repos/nanobot/docs/technical-design-hci-troubleshooting-assistant-v1.md)
- [Development status](/Users/ruibinhuang/repos/nanobot/docs/development-status-v1.md)
- [Skill spec](/Users/ruibinhuang/repos/nanobot/docs/skill-spec-v1.md)
- [Repository slimming plan](/Users/ruibinhuang/repos/nanobot/docs/repository-slimming-plan-v1.md)

## Notes

- The package and CLI command remain `nanobot` for now.
- The assistant persona and current product name are `HCIGuard`.
- This repository is no longer positioned as a generic multi-channel personal assistant.
