"""Execution target parsing and transport helpers for exec."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ExecTarget:
    """Normalized execution target."""

    kind: str
    host: str = ""
    port: int = 22
    username: str = ""


def parse_exec_target(target: str | None) -> ExecTarget:
    """Parse a target string into a normalized execution target."""
    raw = (target or "local").strip()
    if not raw or raw == "local":
        return ExecTarget(kind="local")

    username = ""
    host_port = raw
    if "@" in raw:
        username, host_port = raw.split("@", 1)

    host = host_port
    port = 22
    if ":" in host_port:
        host, port_text = host_port.rsplit(":", 1)
        if port_text:
            port = int(port_text)

    return ExecTarget(
        kind="ssh",
        host=host,
        port=port,
        username=username,
    )


def build_ssh_command(target: ExecTarget, command: str) -> list[str]:
    """Build an SSH argv list for a remote command."""
    if target.kind != "ssh":
        raise ValueError(f"SSH command requires ssh target, got {target.kind!r}")

    destination = f"{target.username}@{target.host}" if target.username else target.host
    argv = ["ssh"]
    if target.port:
        argv.extend(["-p", str(target.port)])
    argv.extend([destination, command])
    return argv


def is_raw_ssh_command(command: str) -> bool:
    """Detect user-provided raw ssh shell commands."""
    return bool(re.match(r"^\s*ssh\b", command))
