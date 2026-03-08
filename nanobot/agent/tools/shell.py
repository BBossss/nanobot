"""Shell execution tool."""

import asyncio
import os
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.security.audit import CommandAuditLogger
from nanobot.security.command_guard import DEFAULT_DENY_PATTERNS, guard_command, load_manual_approvals, extract_base_command


class ExecTool(Tool):
    """Tool to execute shell commands."""

    def __init__(
        self,
        timeout: int = 60,
        working_dir: str | None = None,
        deny_patterns: list[str] | None = None,
        allow_patterns: list[str] | None = None,
        restrict_to_workspace: bool = False,
        path_append: str = "",
        readonly_mode: bool = False,
        allowed_commands: list[str] | None = None,
        approval_file: str | None = None,
    ):
        self.timeout = timeout
        self.working_dir = working_dir
        self.deny_patterns = deny_patterns or list(DEFAULT_DENY_PATTERNS)
        self.allow_patterns = allow_patterns or []
        self.restrict_to_workspace = restrict_to_workspace
        self.path_append = path_append
        self.readonly_mode = readonly_mode
        self.allowed_commands = {c.strip().lower() for c in (allowed_commands or []) if c.strip()}
        self.approval_file = Path(approval_file).expanduser() if approval_file else None
        self.audit = CommandAuditLogger(self.working_dir or os.getcwd())

    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        return "Execute a shell command and return its output. Use with caution."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory for the command"
                }
            },
            "required": ["command"]
        }
    
    async def execute(self, command: str, working_dir: str | None = None, **kwargs: Any) -> str:
        cwd = working_dir or self.working_dir or os.getcwd()
        guard_error = self._guard_command(command, cwd)
        if guard_error:
            self.audit.record(
                source="exec",
                command=command,
                status="blocked",
                cwd=cwd,
                detail=guard_error,
            )
            return guard_error
        
        env = os.environ.copy()
        if self.path_append:
            env["PATH"] = env.get("PATH", "") + os.pathsep + self.path_append

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                # Wait for the process to fully terminate so pipes are
                # drained and file descriptors are released.
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass
                err = f"Error: Command timed out after {self.timeout} seconds"
                self.audit.record(source="exec", command=command, status="timeout", cwd=cwd, detail=err)
                return err
            
            output_parts = []
            
            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))
            
            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"STDERR:\n{stderr_text}")
            
            if process.returncode != 0:
                output_parts.append(f"\nExit code: {process.returncode}")
            
            result = "\n".join(output_parts) if output_parts else "(no output)"
            
            # Truncate very long output
            max_len = 10000
            if len(result) > max_len:
                result = result[:max_len] + f"\n... (truncated, {len(result) - max_len} more chars)"
            self.audit.record(
                source="exec",
                command=command,
                status="ok" if process.returncode == 0 else "error",
                cwd=cwd,
                detail=result,
            )
            return result
            
        except Exception as e:
            err = f"Error executing command: {str(e)}"
            self.audit.record(source="exec", command=command, status="error", cwd=cwd, detail=err)
            return err

    def _guard_command(self, command: str, cwd: str) -> str | None:
        """Best-effort safety guard for potentially destructive commands."""
        return guard_command(
            command,
            cwd=cwd,
            deny_patterns=self.deny_patterns,
            allow_patterns=self.allow_patterns,
            restrict_to_workspace=self.restrict_to_workspace,
            readonly_mode=self.readonly_mode,
            allowed_commands=self.allowed_commands,
            approval_file=self.approval_file,
        )

    def _is_command_allowed(self, command: str) -> bool:
        base = extract_base_command(command)
        if base and base in self.allowed_commands:
            return True
        return command in self._load_manual_approvals()

    def _load_manual_approvals(self) -> set[str]:
        return load_manual_approvals(self.approval_file)
