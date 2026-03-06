#!/usr/bin/env bash
set -euo pipefail

# HCI troubleshooting assistant acceptance script (smoke-level).
# Default mode is "quick" to avoid long-running external integrations.

MODE="quick"          # quick | full
WORKDIR="$(pwd)"
TIMEOUT_SECONDS=45

usage() {
  cat <<'EOF'
Usage:
  scripts/run_hci_acceptance.sh [--mode quick|full] [--workdir PATH]

Modes:
  quick  Local smoke checks only (default)
  full   Includes optional channel/gateway readiness checks
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-quick}"
      shift 2
      ;;
    --workdir)
      WORKDIR="${2:-$(pwd)}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "$MODE" != "quick" && "$MODE" != "full" ]]; then
  echo "Invalid --mode: $MODE" >&2
  exit 1
fi

log() { printf '[CHECK] %s\n' "$*"; }
pass() { printf '[PASS]  %s\n' "$*"; }
fail() { printf '[FAIL]  %s\n' "$*" >&2; exit 1; }

run_cmd() {
  local name="$1"
  shift
  log "$name"
  if "$@"; then
    pass "$name"
  else
    fail "$name"
  fi
}

run_capture() {
  local name="$1"
  shift
  log "$name"
  local out
  if out="$("$@" 2>&1)"; then
    printf '%s\n' "$out"
    pass "$name"
  else
    printf '%s\n' "$out" >&2
    fail "$name"
  fi
}

cd "$WORKDIR"

run_cmd "python exists" command -v python3

if command -v nanobot >/dev/null 2>&1; then
  NB_CMD=(nanobot)
  pass "cli launcher: nanobot"
else
  NB_CMD=(python3 -m nanobot.cli.commands)
  pass "cli launcher: python3 -m nanobot.cli.commands"
fi

CONFIG_PATH="${HOME}/.nanobot/config.json"
if [[ -f "$CONFIG_PATH" ]]; then
  pass "config exists: $CONFIG_PATH"
else
  fail "missing config: $CONFIG_PATH (run: nanobot onboard)"
fi

run_capture "nanobot status" "${NB_CMD[@]}" status
run_capture "cases list command" "${NB_CMD[@]}" cases list --limit 5
run_capture "inspection command (no llm)" "${NB_CMD[@]}" inspection run --no-llm --trigger acceptance
run_capture "approvals list command" "${NB_CMD[@]}" approvals list

run_cmd "diagnostics unit test" python3 -m pytest -q tests/test_diagnostics_tool.py
run_cmd "cases unit test" python3 -m pytest -q tests/test_cases.py
run_cmd "inspection unit test" python3 -m pytest -q tests/test_inspection_service.py
run_cmd "mattermost channel unit test" python3 -m pytest -q tests/test_mattermost_channel.py
run_cmd "readonly approval unit test" python3 -m pytest -q tests/test_exec_readonly_approval.py
run_cmd "session lock unit test" python3 -m pytest -q tests/test_task_cancel.py

if [[ "$MODE" == "full" ]]; then
  log "gateway startup probe (5s)"
  if timeout "$TIMEOUT_SECONDS" "${NB_CMD[@]}" gateway --verbose >/tmp/nanobot_gateway_probe.log 2>&1 &
  then
    GW_PID=$!
    sleep 5
    if ps -p "$GW_PID" >/dev/null 2>&1; then
      pass "gateway process started"
      kill "$GW_PID" >/dev/null 2>&1 || true
      wait "$GW_PID" 2>/dev/null || true
    else
      fail "gateway process did not stay alive"
    fi
  else
    fail "gateway startup probe failed"
  fi
fi

echo
echo "Acceptance script completed: mode=$MODE"
