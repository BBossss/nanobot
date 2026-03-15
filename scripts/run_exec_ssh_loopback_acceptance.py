#!/usr/bin/env python3
"""End-to-end acceptance for local ExecTool SSH loopback targets."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_SSH_LAB = ROOT / "scripts" / "local_ssh_lab.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def build_targets(username: str) -> dict[str, str]:
    """Return the loopback exec targets used by the acceptance run."""
    return {
        "pubkey": f"{username}@127.0.0.1:2322",
        "password": "nanobot@127.0.0.1:2323",
    }


def validate_lab_status(status: dict[str, object]) -> list[str]:
    """Validate that both loopback targets are running before acceptance checks."""
    errors: list[str] = []
    pubkey = status.get("pubkey") or {}
    password = status.get("password") or {}
    if not isinstance(pubkey, dict) or not pubkey.get("running"):
        errors.append("pubkey target is not running")
    if not isinstance(password, dict) or not password.get("running"):
        errors.append("password target is not running")
    return errors


def run_lab_action(action: str) -> dict[str, object]:
    """Run a local SSH lab action and parse the JSON payload."""
    completed = subprocess.run(
        [sys.executable, str(LOCAL_SSH_LAB), action],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.stderr.strip():
        print(completed.stderr.strip(), file=sys.stderr)
    return json.loads(completed.stdout)


def run_direct_pubkey_ssh() -> None:
    """Verify direct SSH to the pubkey loopback target."""
    subprocess.run(
        [
            "ssh",
            "-p",
            "2322",
            "-o",
            "StrictHostKeyChecking=yes",
            "-i",
            str(Path.home() / ".ssh" / "id_rsa"),
            "127.0.0.1",
            "echo ok-direct-pubkey",
        ],
        check=True,
    )


async def run_exec_acceptance() -> dict[str, str]:
    """Verify ExecTool against both loopback SSH targets."""
    from nanobot.agent.tools.shell import ExecTool
    from nanobot.agent.tools.troubleshooting import (
        DiskSnapshotTool,
        NetworkSnapshotTool,
        ReadLogTailTool,
    )

    tool = ExecTool(working_dir=str(ROOT))
    targets = build_targets(getpass.getuser())
    pubkey_result = await tool.execute(
        command="echo ok-exec-pubkey",
        target=targets["pubkey"],
    )
    password_result = await tool.execute(
        command="echo ok-exec-password",
        target=targets["password"],
        ssh_password="secret-123",
    )
    log_tool = ReadLogTailTool()
    disk_tool = DiskSnapshotTool()
    network_tool = NetworkSnapshotTool()
    log_result = await _read_log_tail_with_fallback(log_tool, targets["pubkey"])
    disk_result = await disk_tool.execute(target=targets["pubkey"])
    network_result = await network_tool.execute(target=targets["pubkey"])
    return {
        "pubkey": pubkey_result.strip(),
        "password": password_result.strip(),
        "log_tail": log_result.strip(),
        "disk_snapshot": disk_result.strip(),
        "network_snapshot": network_result.strip(),
    }


async def _read_log_tail_with_fallback(tool: ReadLogTailTool, target: str) -> str:
    """Try a few common log paths and return the first successful tail."""
    candidates = ["/var/log/system.log", "/var/log/syslog", "/var/log/messages"]
    for path in candidates:
        result = await tool.execute(path=path, target=target, lines=20)
        if not result.startswith("Error:"):
            return result
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local ExecTool SSH loopback acceptance")
    parser.add_argument(
        "--keep-running",
        action="store_true",
        help="Leave local SSH lab services running after acceptance succeeds",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    status = {}
    try:
        status = run_lab_action("start")
        errors = validate_lab_status(status)
        if errors:
            raise SystemExit("; ".join(errors))

        print(json.dumps(status, ensure_ascii=False, indent=2))
        run_direct_pubkey_ssh()
        results = asyncio.run(run_exec_acceptance())
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    finally:
        if not args.keep_running:
            run_lab_action("stop")


if __name__ == "__main__":
    raise SystemExit(main())
