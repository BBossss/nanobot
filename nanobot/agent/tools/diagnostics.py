"""Readonly diagnostics tools for troubleshooting workflows."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.security.audit import CommandAuditLogger


class _DiagnosticsBaseTool(Tool):
    """Shared helpers for readonly diagnostics tools."""

    def __init__(
        self,
        *,
        workspace: str | Path | None = None,
        timeout: int = 20,
        max_read_lines: int = 2000,
        max_search_hits: int = 100,
        allowed_paths: list[str] | None = None,
    ):
        self.workspace = Path(workspace).expanduser() if workspace else Path.cwd()
        self.timeout = timeout
        self.max_read_lines = max_read_lines
        self.max_search_hits = max_search_hits
        self.allowed_paths = [Path(p).expanduser().resolve() for p in (allowed_paths or ["/var/log", "/opt/logs"])]
        self.audit = CommandAuditLogger(self.workspace)

    def _record_audit(
        self,
        *,
        source: str,
        detail: str,
        metadata: dict[str, Any],
        status: str = "ok",
    ) -> None:
        self.audit.record(
            source=source,
            command=metadata.get("command", source),
            status=status,
            cwd=str(self.workspace),
            detail=detail,
            metadata=metadata,
        )

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
            self._record_audit(
                source=self.name,
                detail=err,
                metadata={"path": path, "mode": mode, "lines": lines},
                status="blocked",
            )
            return err
        line_count = max(1, min(lines, self.max_read_lines))

        content = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        selected = content[-line_count:] if mode == "tail" else content[:line_count]
        header = f"{mode} {line_count} lines from {file_path}:"
        result = header + ("\n" + "\n".join(selected) if selected else "\n(no content)")
        self._record_audit(
            source=self.name,
            detail=result,
            metadata={"path": str(file_path), "mode": mode, "lines": line_count},
        )
        return result


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
            self._record_audit(
                source=self.name,
                detail=err,
                metadata={"path": path, "pattern": pattern, "max_hits": max_hits},
                status="blocked",
            )
            return err

        flags = re.IGNORECASE if ignore_case else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as exc:
            err = f"Error: Invalid regex pattern: {exc}"
            self._record_audit(
                source=self.name,
                detail=err,
                metadata={"path": str(file_path), "pattern": pattern, "max_hits": max_hits},
                status="error",
            )
            return err

        limit = max(1, min(max_hits, self.max_search_hits))
        matches: list[str] = []
        for line_no, line in enumerate(file_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if regex.search(line):
                matches.append(f"{line_no}: {line}")
            if len(matches) >= limit:
                break

        if not matches:
            result = f"No matches for pattern '{pattern}' in {file_path}"
            self._record_audit(
                source=self.name,
                detail=result,
                metadata={"path": str(file_path), "pattern": pattern, "max_hits": limit},
            )
            return result
        result = f"Found {len(matches)} match(es) in {file_path}:\n" + "\n".join(matches)
        self._record_audit(
            source=self.name,
            detail=result,
            metadata={"path": str(file_path), "pattern": pattern, "max_hits": limit},
        )
        return result


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
            err = f"Error: Unsupported scope '{scope}'"
            self._record_audit(
                source=self.name,
                detail=err,
                metadata={"scope": scope},
                status="error",
            )
            return err

        sections: list[str] = [f"System status scope: {scope}"]
        for cmd in commands:
            output = await self._run_cmd(cmd)
            sections.append(f"$ {' '.join(cmd)}\n{output}")
        result = "\n\n".join(sections)
        self._record_audit(
            source=self.name,
            detail=result,
            metadata={"scope": scope, "command": ", ".join(" ".join(cmd) for cmd in commands)},
        )
        return result
