"""Readonly diagnostics tools for troubleshooting workflows."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool


class _DiagnosticsBaseTool(Tool):
    """Shared helpers for readonly diagnostics tools."""

    def __init__(
        self,
        *,
        timeout: int = 20,
        max_read_lines: int = 2000,
        max_search_hits: int = 100,
        allowed_paths: list[str] | None = None,
    ):
        self.timeout = timeout
        self.max_read_lines = max_read_lines
        self.max_search_hits = max_search_hits
        self.allowed_paths = [Path(p).expanduser().resolve() for p in (allowed_paths or ["/var/log", "/opt/logs"])]

    def _is_path_allowed(self, file_path: Path) -> bool:
        resolved = file_path.expanduser().resolve()
        for allowed in self.allowed_paths:
            if resolved == allowed or allowed in resolved.parents:
                return True
        return False

    def _validate_path(self, path: str) -> tuple[Path | None, str | None]:
        try:
            file_path = Path(path).expanduser().resolve()
        except Exception as exc:
            return None, f"Error: Invalid path '{path}': {exc}"

        if not self._is_path_allowed(file_path):
            allowed = ", ".join(str(p) for p in self.allowed_paths)
            return None, f"Error: Path '{path}' is outside allowed paths ({allowed})"
        if not file_path.exists():
            return None, f"Error: File not found: {path}"
        if not file_path.is_file():
            return None, f"Error: Not a file: {path}"
        return file_path, None

    async def _run_cmd(self, args: list[str]) -> str:
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
                return f"Error: Command timed out after {self.timeout}s: {' '.join(args)}"
            out = stdout.decode("utf-8", errors="replace").strip()
            err = stderr.decode("utf-8", errors="replace").strip()
            if process.returncode != 0:
                details = err or out or "(no output)"
                return f"Error: Command failed ({process.returncode}): {' '.join(args)}\n{details}"
            return out or "(no output)"
        except FileNotFoundError:
            return f"Error: Command not available: {args[0]}"
        except Exception as exc:
            return f"Error executing command {' '.join(args)}: {exc}"


class DiagnoseLogReadTool(_DiagnosticsBaseTool):
    """Read log snippets from allowed paths."""

    @property
    def name(self) -> str:
        return "diagnose_log_read"

    @property
    def description(self) -> str:
        return "Read a bounded number of lines from an allowed log file."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the log file"},
                "lines": {"type": "integer", "minimum": 1, "maximum": 2000},
                "mode": {"type": "string", "enum": ["tail", "head"]},
            },
            "required": ["path"],
        }

    async def execute(self, path: str, lines: int = 200, mode: str = "tail", **kwargs: Any) -> str:
        file_path, err = self._validate_path(path)
        if err:
            return err
        line_count = max(1, min(lines, self.max_read_lines))

        content = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        selected = content[-line_count:] if mode == "tail" else content[:line_count]
        header = f"{mode} {line_count} lines from {file_path}:"
        return header + ("\n" + "\n".join(selected) if selected else "\n(no content)")


class DiagnoseLogSearchTool(_DiagnosticsBaseTool):
    """Search patterns in allowed logs with bounded output."""

    @property
    def name(self) -> str:
        return "diagnose_log_search"

    @property
    def description(self) -> str:
        return "Search an allowed log file with regex and return bounded matches with line numbers."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the log file"},
                "pattern": {"type": "string", "minLength": 1, "description": "Regex pattern to search"},
                "max_hits": {"type": "integer", "minimum": 1, "maximum": 100},
                "ignore_case": {"type": "boolean"},
            },
            "required": ["path", "pattern"],
        }

    async def execute(
        self,
        path: str,
        pattern: str,
        max_hits: int = 50,
        ignore_case: bool = True,
        **kwargs: Any,
    ) -> str:
        file_path, err = self._validate_path(path)
        if err:
            return err

        flags = re.IGNORECASE if ignore_case else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as exc:
            return f"Error: Invalid regex pattern: {exc}"

        limit = max(1, min(max_hits, self.max_search_hits))
        matches: list[str] = []
        for line_no, line in enumerate(file_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if regex.search(line):
                matches.append(f"{line_no}: {line}")
            if len(matches) >= limit:
                break

        if not matches:
            return f"No matches for pattern '{pattern}' in {file_path}"
        return f"Found {len(matches)} match(es) in {file_path}:\n" + "\n".join(matches)


class DiagnoseSystemStatusTool(_DiagnosticsBaseTool):
    """Collect bounded readonly status snapshots."""

    _SCOPE_COMMANDS: dict[str, list[list[str]]] = {
        "general": [["uptime"], ["df", "-h"]],
        "memory": [["free", "-m"], ["vm_stat"]],
        "process": [["ps", "-eo", "pid,ppid,comm,%cpu,%mem", "--sort=-%cpu"]],
        "network": [["ss", "-tuln"], ["netstat", "-an"]],
        "disk": [["df", "-h"], ["iostat"]],
    }

    @property
    def name(self) -> str:
        return "diagnose_system_status"

    @property
    def description(self) -> str:
        return "Collect readonly system status for a fixed scope (general, memory, process, network, disk)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["general", "memory", "process", "network", "disk"],
                }
            },
            "required": ["scope"],
        }

    async def execute(self, scope: str, **kwargs: Any) -> str:
        commands = self._SCOPE_COMMANDS.get(scope)
        if not commands:
            return f"Error: Unsupported scope '{scope}'"

        sections: list[str] = [f"System status scope: {scope}"]
        for cmd in commands:
            output = await self._run_cmd(cmd)
            sections.append(f"$ {' '.join(cmd)}\n{output}")
        return "\n\n".join(sections)
