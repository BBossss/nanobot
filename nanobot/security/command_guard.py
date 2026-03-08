"""Shared command safety and approval helpers."""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path


DEFAULT_DENY_PATTERNS = [
    r"\brm\s+-[rf]{1,2}\b",
    r"\bdel\s+/[fq]\b",
    r"\brmdir\s+/s\b",
    r"(?:^|[;&|]\s*)format\b",
    r"\b(mkfs|diskpart)\b",
    r"\bdd\s+if=",
    r">\s*/dev/sd",
    r"\b(shutdown|reboot|poweroff)\b",
    r":\(\)\s*\{.*\};\s*:",
]


def load_manual_approvals(path: Path | None) -> set[str]:
    """Load exact command approvals from disk."""
    if not path or not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        commands = data.get("commands", [])
        if isinstance(commands, list):
            return {str(c) for c in commands if str(c).strip()}
    except Exception:
        return set()
    return set()


def extract_base_command(command: str) -> str:
    """Return the first command token."""
    cmd = command.strip()
    if not cmd:
        return ""
    return re.split(r"\s+", cmd, maxsplit=1)[0].strip().lower()


def extract_absolute_paths(command: str) -> list[str]:
    """Extract explicit absolute paths from a command string."""
    win_paths = re.findall(r"[A-Za-z]:\\[^\s\"'|><;]+", command)
    posix_paths = re.findall(r"(?:^|[\s|>])(/[^\s\"'>]+)", command)
    return win_paths + posix_paths


def is_command_allowed(
    command: str,
    *,
    allowed_commands: set[str] | None = None,
    approval_file: Path | None = None,
) -> bool:
    """Check readonly-mode allowlist plus exact manual approvals."""
    base = extract_base_command(command)
    if base and allowed_commands and base in allowed_commands:
        return True
    return command in load_manual_approvals(approval_file)


_SSH_OPTIONS_WITH_VALUE = {
    "-b",
    "-c",
    "-D",
    "-E",
    "-e",
    "-F",
    "-i",
    "-J",
    "-L",
    "-l",
    "-m",
    "-o",
    "-p",
    "-Q",
    "-R",
    "-S",
    "-W",
    "-w",
}


def normalize_ssh_host(destination: str) -> str:
    """Normalize ssh destination to bare host for allowlist checks."""
    host = destination.rsplit("@", 1)[-1]
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    return host.strip().lower()


def parse_ssh_command(command: str) -> tuple[str, str] | None:
    """Parse a simple ssh command into (destination, remote_command)."""
    try:
        parts = shlex.split(command)
    except ValueError:
        return None

    if not parts or parts[0].lower() != "ssh":
        return None

    idx = 1
    destination = ""
    while idx < len(parts):
        token = parts[idx]
        if token == "--":
            idx += 1
            continue
        if token.startswith("-"):
            short = token[:2]
            if token in _SSH_OPTIONS_WITH_VALUE:
                idx += 2
                continue
            if short in _SSH_OPTIONS_WITH_VALUE and len(token) > 2:
                idx += 1
                continue
            idx += 1
            continue
        destination = token
        idx += 1
        break

    remote_tokens = parts[idx:]
    if not destination or not remote_tokens:
        return None
    return destination, shlex.join(remote_tokens)


def guard_command(
    command: str,
    *,
    cwd: str,
    deny_patterns: list[str] | None = None,
    allow_patterns: list[str] | None = None,
    restrict_to_workspace: bool = False,
    readonly_mode: bool = False,
    allowed_commands: set[str] | None = None,
    approval_file: Path | None = None,
    allow_ssh_bridge: bool = False,
    allowed_ssh_hosts: set[str] | None = None,
) -> str | None:
    """Apply shared command safety rules. Returns an error string when blocked."""
    cmd = command.strip()
    lower = cmd.lower()

    for pattern in (deny_patterns or DEFAULT_DENY_PATTERNS):
        if re.search(pattern, lower):
            return "Error: Command blocked by safety guard (dangerous pattern detected)"

    if allow_patterns:
        if not any(re.search(p, lower) for p in allow_patterns):
            return "Error: Command blocked by safety guard (not in allowlist)"

    if readonly_mode and extract_base_command(cmd) == "ssh" and allow_ssh_bridge:
        if cmd in load_manual_approvals(approval_file):
            return None
        parsed = parse_ssh_command(cmd)
        if not parsed:
            return "Error: SSH bridge requires a destination and a remote command"
        destination, remote_command = parsed
        remote_host = normalize_ssh_host(destination)
        if allowed_ssh_hosts and remote_host not in {h.strip().lower() for h in allowed_ssh_hosts if h.strip()}:
            return f"Error: SSH target '{remote_host}' is not in the approved host list"
        remote_allowed = {c for c in (allowed_commands or set()) if c != "ssh"}
        return guard_command(
            remote_command,
            cwd=cwd,
            deny_patterns=deny_patterns,
            allow_patterns=None,
            restrict_to_workspace=False,
            readonly_mode=True,
            allowed_commands=remote_allowed,
            approval_file=approval_file,
            allow_ssh_bridge=False,
            allowed_ssh_hosts=None,
        )

    if readonly_mode and not is_command_allowed(
        cmd,
        allowed_commands=allowed_commands,
        approval_file=approval_file,
    ):
        return (
            "Error: Command requires manual approval in readonly mode. "
            f"Approve it with: nanobot approvals grant --command {cmd!r}"
        )

    if restrict_to_workspace:
        if "..\\" in cmd or "../" in cmd:
            return "Error: Command blocked by safety guard (path traversal detected)"

        cwd_path = Path(cwd).resolve()
        for raw in extract_absolute_paths(cmd):
            try:
                p = Path(raw.strip()).resolve()
            except Exception:
                continue
            if p.is_absolute() and cwd_path not in p.parents and p != cwd_path:
                return "Error: Command blocked by safety guard (path outside working dir)"

    return None
