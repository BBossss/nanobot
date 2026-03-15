"""Target-aware troubleshooting tools."""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from nanobot.agent.tools.exec_transport import (
    ExecTarget,
    build_ssh_command,
    is_raw_ssh_command,
    parse_exec_target,
)

from nanobot.agent.tools.base import Tool


class _BaseTroubleshootingTool(Tool):
    """Shared helpers for troubleshooting tools."""

    def __init__(
        self,
        *,
        timeout: int = 20,
        allowed_log_roots: list[str | Path] | None = None,
    ):
        self.timeout = timeout
        self.allowed_log_roots = self._normalize_roots(allowed_log_roots or [])

    @staticmethod
    def _normalize_roots(roots: list[str | Path]) -> list[Path]:
        normalized: list[Path] = []
        for root in roots:
            try:
                p = Path(root).expanduser().resolve()
            except Exception:
                p = Path(str(root)).expanduser()
            normalized.append(p)
        return normalized

    def _is_path_allowed(self, path: Path) -> bool:
        for root in self.allowed_log_roots:
            if path == root or root in path.parents:
                return True
        return False

    def _is_path_allowed_str(self, path: str) -> bool:
        for root in self.allowed_log_roots:
            root_str = str(root).rstrip("/")
            if path == root_str or path.startswith(root_str + "/"):
                return True
        return False

    def _validate_log_path(self, path: str) -> tuple[Path | None, str | None]:
        try:
            resolved = Path(path).expanduser().resolve()
        except Exception as exc:
            return None, f"Error: Invalid path '{path}': {exc}"
        if not self._is_path_allowed(resolved):
            allowed = ", ".join(str(p) for p in self.allowed_log_roots) or "(none)"
            return None, f"Error: Path '{path}' is outside allowed log roots ({allowed})"
        if not resolved.exists():
            return None, f"Error: File not found: {path}"
        if not resolved.is_file():
            return None, f"Error: Not a file: {path}"
        return resolved, None

    async def _run_process(self, args: list[str]) -> tuple[str, str, int]:
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return "", f"Error: Command timed out after {self.timeout}s", -1
            out = stdout.decode("utf-8", errors="replace").strip()
            err = stderr.decode("utf-8", errors="replace").strip()
            return out, err, process.returncode or 0
        except FileNotFoundError:
            return "", "Error: Command not available", 127
        except Exception as exc:
            return "", f"Error executing command: {exc}", 1

    async def _run_remote_command(self, target: ExecTarget, command: str) -> tuple[str, str, int]:
        argv = build_ssh_command(target, command)
        return await self._run_process(argv)

    async def execute(self, **kwargs: Any) -> str:
        return "Error: Tool not implemented yet."


@dataclass(frozen=True)
class TargetCommandRunner:
    """Minimal target-aware runner for troubleshooting tools."""

    default_target: str
    ssh_enabled: bool
    run_local: Callable[..., Awaitable[str]]
    run_remote: Callable[..., Awaitable[str]]

    def parse_target(self, target: str | None) -> ExecTarget:
        return parse_exec_target(target or self.default_target)

    async def run(self, *, command: str, target: str | None = None, **kwargs: Any) -> str:
        exec_target = self.parse_target(target)
        if exec_target.kind == "local" and is_raw_ssh_command(command):
            return (
                "Error: Raw ssh commands are not allowed here. Use target='user@host[:port]' "
                "with a normal command instead."
            )
        if exec_target.kind == "local":
            return await self.run_local(command=command, **kwargs)
        if not self.ssh_enabled:
            return "Error: SSH execution is disabled for troubleshooting tools."
        return await self.run_remote(target=exec_target, command=command, **kwargs)


def _build_target_runner(*, default_target: str, ssh_enabled: bool) -> TargetCommandRunner:
    async def _run_local_stub(**kwargs: Any) -> str:
        return "Error: Tool not implemented yet."

    async def _run_remote_stub(**kwargs: Any) -> str:
        return "Error: Tool not implemented yet."

    return TargetCommandRunner(
        default_target=default_target,
        ssh_enabled=ssh_enabled,
        run_local=_run_local_stub,
        run_remote=_run_remote_stub,
    )


class FindLogsTool(_BaseTroubleshootingTool):
    def __init__(
        self,
        *,
        allowed_log_roots: list[str | Path] | None = None,
        max_results: int = 20,
        timeout: int = 20,
        default_target: str = "local",
        ssh_enabled: bool = True,
    ):
        super().__init__(
            timeout=timeout,
            allowed_log_roots=allowed_log_roots or ["/var/log", "/opt/logs", "/sf/log"],
        )
        self.max_results = max_results
        self.default_target = default_target
        self.ssh_enabled = ssh_enabled

    @property
    def name(self) -> str:
        return "find_logs"

    @property
    def description(self) -> str:
        return "Find log files by keyword under allowed log roots."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "minLength": 1},
                "target": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["keyword"],
        }

    async def execute(
        self,
        keyword: str,
        target: str | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ) -> str:
        needle = keyword.strip()
        if not needle:
            return "Error: keyword must not be empty."
        cap = max(1, min(limit or self.max_results, self.max_results))
        target_label = target or self.default_target
        exec_target = parse_exec_target(target_label)
        if exec_target.kind == "ssh" and not self.ssh_enabled:
            return "Error: SSH execution is disabled for troubleshooting tools."

        if exec_target.kind == "local":
            matches: list[str] = []
            for root in self.allowed_log_roots:
                if not root.exists():
                    continue
                for dirpath, _dirnames, filenames in os.walk(root):
                    for name in filenames:
                        if needle.lower() in name.lower():
                            matches.append(os.path.join(dirpath, name))
                            if len(matches) >= cap:
                                break
                    if len(matches) >= cap:
                        break
                if len(matches) >= cap:
                    break
        else:
            matches = []
            pattern = f"*{needle}*"
            for root in self.allowed_log_roots:
                remaining = cap - len(matches)
                if remaining <= 0:
                    break
                cmd = (
                    f"find {shlex.quote(str(root))} -type f -iname "
                    f"{shlex.quote(pattern)} 2>/dev/null | head -n {remaining}"
                )
                out, err, code = await self._run_remote_command(exec_target, cmd)
                if code != 0 and err:
                    return f"[target={target_label}] Error: {err}"
                if out:
                    matches.extend([line for line in out.splitlines() if line.strip()])
                if len(matches) >= cap:
                    break

        if not matches:
            return f"[target={target_label}] No log files found for keyword '{needle}'."
        return (
            f"[target={target_label}] find_logs('{needle}') returned {len(matches)} result(s):\n"
            + "\n".join(matches[:cap])
        )


class ReadLogTailTool(_BaseTroubleshootingTool):
    def __init__(
        self,
        *,
        default_lines: int = 200,
        max_lines: int = 2000,
        timeout: int = 20,
        allowed_log_roots: list[str | Path] | None = None,
        default_target: str = "local",
        ssh_enabled: bool = True,
    ):
        super().__init__(
            timeout=timeout,
            allowed_log_roots=allowed_log_roots or ["/var/log", "/opt/logs", "/sf/log"],
        )
        self.default_lines = default_lines
        self.max_lines = max_lines
        self.default_target = default_target
        self.ssh_enabled = ssh_enabled

    @property
    def name(self) -> str:
        return "read_log_tail"

    @property
    def description(self) -> str:
        return "Read the tail of a log file on a local or remote target."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "target": {"type": "string"},
                "lines": {"type": "integer", "minimum": 1, "maximum": 2000},
            },
            "required": ["path"],
        }

    async def execute(
        self,
        path: str,
        target: str | None = None,
        lines: int | None = None,
        **kwargs: Any,
    ) -> str:
        line_count = max(1, min(lines or self.default_lines, self.max_lines))
        target_label = target or self.default_target
        exec_target = parse_exec_target(target_label)
        if exec_target.kind == "ssh" and not self.ssh_enabled:
            return "Error: SSH execution is disabled for troubleshooting tools."

        if exec_target.kind == "local":
            file_path, err = self._validate_log_path(path)
            if err:
                return err
            content = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            selected = content[-line_count:]
            header = f"[target={target_label}] tail {line_count} lines from {file_path}:"
            return header + ("\n" + "\n".join(selected) if selected else "\n(no content)")

        if not self._is_path_allowed_str(path):
            allowed = ", ".join(str(p) for p in self.allowed_log_roots) or "(none)"
            return f"Error: Path '{path}' is outside allowed log roots ({allowed})"

        cmd = f"tail -n {line_count} {shlex.quote(path)}"
        out, err, code = await self._run_remote_command(exec_target, cmd)
        if code != 0:
            details = err or out or "(no output)"
            return f"[target={target_label}] Error: {details}"
        header = f"[target={target_label}] tail {line_count} lines from {path}:"
        return header + ("\n" + out if out else "\n(no output)")


class SearchLogTool(_BaseTroubleshootingTool):
    def __init__(
        self,
        *,
        max_hits: int = 100,
        timeout: int = 20,
        allowed_log_roots: list[str | Path] | None = None,
        default_target: str = "local",
        ssh_enabled: bool = True,
    ):
        super().__init__(
            timeout=timeout,
            allowed_log_roots=allowed_log_roots or ["/var/log", "/opt/logs", "/sf/log"],
        )
        self.max_hits = max_hits
        self.default_target = default_target
        self.ssh_enabled = ssh_enabled

    @property
    def name(self) -> str:
        return "search_log"

    @property
    def description(self) -> str:
        return "Search a log file with a regex pattern on a local or remote target."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "pattern": {"type": "string", "minLength": 1},
                "target": {"type": "string"},
                "max_hits": {"type": "integer", "minimum": 1, "maximum": 200},
                "ignore_case": {"type": "boolean"},
            },
            "required": ["path", "pattern"],
        }

    async def execute(
        self,
        path: str,
        pattern: str,
        target: str | None = None,
        max_hits: int | None = None,
        ignore_case: bool = True,
        **kwargs: Any,
    ) -> str:
        limit = max(1, min(max_hits or self.max_hits, self.max_hits))
        target_label = target or self.default_target
        exec_target = parse_exec_target(target_label)
        if exec_target.kind == "ssh" and not self.ssh_enabled:
            return "Error: SSH execution is disabled for troubleshooting tools."

        if exec_target.kind == "local":
            file_path, err = self._validate_log_path(path)
            if err:
                return err
            flags = re.IGNORECASE if ignore_case else 0
            try:
                regex = re.compile(pattern, flags)
            except re.error as exc:
                return f"Error: Invalid regex pattern: {exc}"
            matches: list[str] = []
            for line_no, line in enumerate(
                file_path.read_text(encoding="utf-8", errors="replace").splitlines(),
                start=1,
            ):
                if regex.search(line):
                    matches.append(f"{line_no}: {line}")
                if len(matches) >= limit:
                    break
            if not matches:
                return f"No matches for pattern '{pattern}' in {file_path}"
            return f"[target={target_label}] Found {len(matches)} match(es) in {file_path}:\n" + "\n".join(matches)

        if not self._is_path_allowed_str(path):
            allowed = ", ".join(str(p) for p in self.allowed_log_roots) or "(none)"
            return f"Error: Path '{path}' is outside allowed log roots ({allowed})"

        flags = "-i" if ignore_case else ""
        cmd = (
            f"grep -nE {flags} {shlex.quote(pattern)} {shlex.quote(path)} | "
            f"head -n {limit}"
        )
        out, err, code = await self._run_remote_command(exec_target, cmd)
        if code != 0 and not out:
            if err:
                return f"[target={target_label}] Error: {err}"
            return f"No matches for pattern '{pattern}' in {path}"
        if not out:
            return f"No matches for pattern '{pattern}' in {path}"
        return f"[target={target_label}] Found matches in {path}:\n" + out


class JournalTailTool(_BaseTroubleshootingTool):
    def __init__(
        self,
        *,
        default_lines: int = 200,
        max_lines: int = 2000,
        timeout: int = 20,
        default_target: str = "local",
        ssh_enabled: bool = True,
    ):
        super().__init__(timeout=timeout, allowed_log_roots=["/var/log", "/opt/logs", "/sf/log"])
        self.default_lines = default_lines
        self.max_lines = max_lines
        self.default_target = default_target
        self.ssh_enabled = ssh_enabled

    @property
    def name(self) -> str:
        return "journal_tail"

    @property
    def description(self) -> str:
        return "Read recent journal lines for a systemd service."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "service": {"type": "string", "minLength": 1},
                "target": {"type": "string"},
                "lines": {"type": "integer", "minimum": 1, "maximum": 2000},
            },
            "required": ["service"],
        }

    async def execute(
        self,
        service: str,
        target: str | None = None,
        lines: int | None = None,
        **kwargs: Any,
    ) -> str:
        line_count = max(1, min(lines or self.default_lines, self.max_lines))
        target_label = target or self.default_target
        exec_target = parse_exec_target(target_label)
        if exec_target.kind == "ssh" and not self.ssh_enabled:
            return "Error: SSH execution is disabled for troubleshooting tools."

        args = ["journalctl", "-u", service, "-n", str(line_count), "--no-pager"]
        if exec_target.kind == "local":
            out, err, code = await self._run_process(args)
        else:
            cmd = " ".join(shlex.quote(arg) for arg in args)
            out, err, code = await self._run_remote_command(exec_target, cmd)
        details = out or err or "(no output)"
        return f"[target={target_label}] journal_tail({service})\n{details}"


class DiskSnapshotTool(_BaseTroubleshootingTool):
    def __init__(
        self,
        *,
        timeout: int = 20,
        default_target: str = "local",
        ssh_enabled: bool = True,
    ):
        super().__init__(timeout=timeout, allowed_log_roots=["/var/log", "/opt/logs", "/sf/log"])
        self.default_target = default_target
        self.ssh_enabled = ssh_enabled

    @property
    def name(self) -> str:
        return "disk_snapshot"

    @property
    def description(self) -> str:
        return "Collect a readonly disk snapshot."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
            },
            "required": [],
        }

    async def execute(self, target: str | None = None, **kwargs: Any) -> str:
        target_label = target or self.default_target
        exec_target = parse_exec_target(target_label)
        if exec_target.kind == "ssh" and not self.ssh_enabled:
            return "Error: SSH execution is disabled for troubleshooting tools."

        if exec_target.kind == "local":
            out, err, _code = await self._run_process(["df", "-h"])
        else:
            out, err, _code = await self._run_remote_command(exec_target, "df -h")
        details = out or err or "(no output)"
        return f"[target={target_label}] disk_snapshot\n{details}"


class NetworkSnapshotTool(_BaseTroubleshootingTool):
    def __init__(
        self,
        *,
        timeout: int = 20,
        default_target: str = "local",
        ssh_enabled: bool = True,
    ):
        super().__init__(timeout=timeout, allowed_log_roots=["/var/log", "/opt/logs", "/sf/log"])
        self.default_target = default_target
        self.ssh_enabled = ssh_enabled

    @property
    def name(self) -> str:
        return "network_snapshot"

    @property
    def description(self) -> str:
        return "Collect a readonly network snapshot."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
            },
            "required": [],
        }

    async def execute(self, target: str | None = None, **kwargs: Any) -> str:
        target_label = target or self.default_target
        exec_target = parse_exec_target(target_label)
        if exec_target.kind == "ssh" and not self.ssh_enabled:
            return "Error: SSH execution is disabled for troubleshooting tools."

        cmd = "ss -tuln || netstat -an"
        if exec_target.kind == "local":
            out, err, _code = await self._run_process(["/bin/sh", "-c", cmd])
        else:
            out, err, _code = await self._run_remote_command(exec_target, cmd)
        details = out or err or "(no output)"
        return f"[target={target_label}] network_snapshot\n{details}"


class FindRecentFilesTool(_BaseTroubleshootingTool):
    def __init__(
        self,
        *,
        timeout: int = 20,
        default_target: str = "local",
        ssh_enabled: bool = True,
        allowed_log_roots: list[str | Path] | None = None,
        max_results: int = 50,
    ):
        super().__init__(
            timeout=timeout,
            allowed_log_roots=allowed_log_roots or ["/var/log", "/opt/logs", "/sf/log"],
        )
        self.default_target = default_target
        self.ssh_enabled = ssh_enabled
        self.max_results = max_results

    @property
    def name(self) -> str:
        return "find_recent_files"

    @property
    def description(self) -> str:
        return "Find recent files under a base path within a time window."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "base_path": {"type": "string", "minLength": 1},
                "minutes": {"type": "integer", "minimum": 1, "maximum": 1440},
                "target": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["base_path"],
        }

    async def execute(
        self,
        base_path: str,
        target: str | None = None,
        minutes: int = 60,
        limit: int | None = None,
        **kwargs: Any,
    ) -> str:
        target_label = target or self.default_target
        exec_target = parse_exec_target(target_label)
        if exec_target.kind == "ssh" and not self.ssh_enabled:
            return "Error: SSH execution is disabled for troubleshooting tools."

        cap = max(1, min(limit or self.max_results, self.max_results))
        if not self._is_path_allowed_str(base_path):
            allowed = ", ".join(str(p) for p in self.allowed_log_roots) or "(none)"
            return f"Error: Path '{base_path}' is outside allowed log roots ({allowed})"

        if exec_target.kind == "local":
            root = Path(base_path).expanduser()
            if not root.exists():
                return f"Error: Path not found: {base_path}"
            cutoff = (time.time() - minutes * 60)
            matches: list[str] = []
            for dirpath, _dirnames, filenames in os.walk(root):
                for name in filenames:
                    p = Path(dirpath) / name
                    try:
                        if p.stat().st_mtime >= cutoff:
                            matches.append(str(p))
                    except OSError:
                        continue
                    if len(matches) >= cap:
                        break
                if len(matches) >= cap:
                    break
        else:
            cmd = (
                f"find {shlex.quote(base_path)} -type f -mmin -{minutes} "
                f"2>/dev/null | head -n {cap}"
            )
            out, err, code = await self._run_remote_command(exec_target, cmd)
            if code != 0 and err:
                return f"[target={target_label}] Error: {err}"
            matches = [line for line in (out or "").splitlines() if line.strip()]

        if not matches:
            return f"[target={target_label}] No recent files found under {base_path}."
        return (
            f"[target={target_label}] find_recent_files({base_path}) returned {len(matches)} result(s):\n"
            + "\n".join(matches[:cap])
        )


class ServiceStatusTool(_BaseTroubleshootingTool):
    def __init__(
        self,
        *,
        timeout: int = 20,
        default_target: str = "local",
        ssh_enabled: bool = True,
    ):
        super().__init__(timeout=timeout, allowed_log_roots=["/var/log", "/opt/logs", "/sf/log"])
        self.default_target = default_target
        self.ssh_enabled = ssh_enabled

    @property
    def name(self) -> str:
        return "service_status"

    @property
    def description(self) -> str:
        return "Check service status on a local or remote target."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "service": {"type": "string", "minLength": 1},
                "target": {"type": "string"},
            },
            "required": ["service"],
        }

    async def execute(
        self,
        service: str,
        target: str | None = None,
        **kwargs: Any,
    ) -> str:
        target_label = target or self.default_target
        exec_target = parse_exec_target(target_label)
        if exec_target.kind == "ssh" and not self.ssh_enabled:
            return "Error: SSH execution is disabled for troubleshooting tools."

        systemctl_args = ["systemctl", "status", "--no-pager", service]
        if exec_target.kind == "local":
            out, err, code = await self._run_process(systemctl_args)
        else:
            cmd = " ".join(shlex.quote(arg) for arg in systemctl_args)
            out, err, code = await self._run_remote_command(exec_target, cmd)

        if code != 0:
            fallback_cmd = (
                f"ps -ef | grep -i -- {shlex.quote(service)} | grep -v grep"
            )
            if exec_target.kind == "local":
                out, err, code = await self._run_process(["/bin/sh", "-c", fallback_cmd])
            else:
                out, err, code = await self._run_remote_command(exec_target, fallback_cmd)

        details = out or err or "(no output)"
        return f"[target={target_label}] service_status({service})\n{details}"


class ProcessSnapshotTool(_BaseTroubleshootingTool):
    def __init__(
        self,
        *,
        max_processes: int = 20,
        timeout: int = 20,
        default_target: str = "local",
        ssh_enabled: bool = True,
    ):
        super().__init__(timeout=timeout, allowed_log_roots=["/var/log", "/opt/logs", "/sf/log"])
        self.max_processes = max_processes
        self.default_target = default_target
        self.ssh_enabled = ssh_enabled

    @property
    def name(self) -> str:
        return "process_snapshot"

    @property
    def description(self) -> str:
        return "Collect a bounded process snapshot from a local or remote target."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": [],
        }

    async def execute(
        self,
        target: str | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ) -> str:
        target_label = target or self.default_target
        exec_target = parse_exec_target(target_label)
        if exec_target.kind == "ssh" and not self.ssh_enabled:
            return "Error: SSH execution is disabled for troubleshooting tools."

        cap = max(1, min(limit or self.max_processes, self.max_processes))
        cmd = (
            "ps -eo pid,ppid,comm,%cpu,%mem --sort=-%cpu | "
            f"head -n {cap + 1}"
        )
        if exec_target.kind == "local":
            out, err, _code = await self._run_process(["/bin/sh", "-c", cmd])
        else:
            out, err, _code = await self._run_remote_command(exec_target, cmd)
        details = out or err or "(no output)"
        return f"[target={target_label}] process_snapshot\n{details}"
