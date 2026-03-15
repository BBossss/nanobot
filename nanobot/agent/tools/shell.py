"""Shell execution tool."""

import asyncio
import os
import re
import shutil
from pathlib import Path
from typing import Any, Awaitable, Callable

from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.exec_transport import (
    ExecTarget,
    build_ssh_command,
    is_raw_ssh_command,
    parse_exec_target,
)
from nanobot.security.audit import CommandAuditLogger
from nanobot.security.command_guard import (
    DEFAULT_DENY_PATTERNS,
    extract_absolute_paths,
    extract_base_command,
    guard_command,
    load_manual_approvals,
)


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
        default_target: str = "local",
        ssh_enabled: bool = True,
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
        self.default_target = default_target
        self.ssh_enabled = ssh_enabled
        self._context_channel = "cli"
        self._context_chat_id = "direct"
        self._secret_prompt_callback: Callable[[str], Awaitable[str | None]] | None = None
        self._ssh_password_cache: dict[str, str] = {}
        self.audit = CommandAuditLogger(self.working_dir or os.getcwd())

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set current execution context for prompt routing."""
        self._context_channel = channel
        self._context_chat_id = chat_id

    def set_secret_prompt_callback(
        self,
        callback: Callable[[str], Awaitable[str | None]] | None,
    ) -> None:
        """Set the callback used to request secrets during CLI troubleshooting."""
        self._secret_prompt_callback = callback

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
                },
                "target": {
                    "type": "string",
                    "description": "Execution target. Use 'local' for the current machine or 'user@host[:port]' for SSH."
                },
                "ssh_password": {
                    "type": "string",
                    "description": "Optional SSH password for password-based login. This value is kept in process memory only."
                },
            },
            "required": ["command"]
        }
    
    async def execute(
        self,
        command: str,
        working_dir: str | None = None,
        target: str | None = None,
        ssh_password: str | None = None,
        **kwargs: Any,
    ) -> str:
        cwd = working_dir or self.working_dir or os.getcwd()
        exec_target = parse_exec_target(target or self.default_target)
        target_label = target or self.default_target
        effective_password = ssh_password or self._ssh_password_cache.get(target_label)
        if exec_target.kind == "local" and is_raw_ssh_command(command):
            err = "Error: Raw ssh commands are not allowed here. Use target='user@host[:port]' with a normal command instead."
            self.audit.record(
                source="exec",
                command=command,
                status="blocked",
                cwd=cwd,
                detail=err,
                metadata={"target": target_label, "transport": exec_target.kind},
            )
            return err
        guard_error = self._guard_command(command, cwd)
        if guard_error:
            self.audit.record(
                source="exec",
                command=command,
                status="blocked",
                cwd=cwd,
                detail=guard_error,
                metadata={"target": target_label, "transport": exec_target.kind},
            )
            return guard_error
        
        env = os.environ.copy()
        if self.path_append:
            env["PATH"] = env.get("PATH", "") + os.pathsep + self.path_append
        if effective_password:
            env["NANOBOT_SSH_PASSWORD"] = effective_password

        try:
            if exec_target.kind == "local":
                result, status = await self._run_local_command(
                    command=command,
                    cwd=cwd,
                    timeout=self.timeout,
                    env=env,
                )
            else:
                if not self.ssh_enabled:
                    result = "Error: SSH execution is disabled for exec."
                    status = "blocked"
                else:
                    remote_result = await self._run_remote_command(
                        target=exec_target,
                        command=command,
                        timeout=self.timeout,
                        env=env,
                    )
                    if isinstance(remote_result, tuple):
                        result, status = remote_result
                    else:
                        result = remote_result
                        status = "error" if str(result).startswith("Error:") else "ok"
                    if self._should_prompt_for_ssh_password(
                        target=exec_target,
                        status=status,
                        result=result,
                        ssh_password=effective_password,
                    ):
                        prompted_password = await self._prompt_for_ssh_password(target_label)
                        if prompted_password:
                            self._ssh_password_cache[target_label] = prompted_password
                            retry_env = env.copy()
                            retry_env["NANOBOT_SSH_PASSWORD"] = prompted_password
                            retry_result = await self._run_remote_command(
                                target=exec_target,
                                command=command,
                                timeout=self.timeout,
                                env=retry_env,
                            )
                            if isinstance(retry_result, tuple):
                                result, status = retry_result
                            else:
                                result = retry_result
                                status = "error" if str(result).startswith("Error:") else "ok"
            self.audit.record(
                source="exec",
                command=command,
                status=status,
                cwd=cwd,
                detail=result,
                metadata={"target": target_label, "transport": exec_target.kind},
            )
            return result
            
        except Exception as e:
            err = f"Error executing command: {str(e)}"
            self.audit.record(
                source="exec",
                command=command,
                status="error",
                cwd=cwd,
                detail=err,
                metadata={"target": target_label, "transport": exec_target.kind},
            )
            return err

    async def _run_local_command(
        self,
        *,
        command: str,
        cwd: str,
        timeout: int,
        env: dict[str, str],
    ) -> tuple[str, str]:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        return await self._communicate_and_format(process=process, timeout=timeout)

    async def _run_remote_command(
        self,
        *,
        target: ExecTarget,
        command: str,
        timeout: int,
        env: dict[str, str],
    ) -> tuple[str, str]:
        argv = build_ssh_command(target, command)
        if env.get("NANOBOT_SSH_PASSWORD"):
            if shutil.which("sshpass"):
                argv = ["sshpass", "-e", *argv]
            elif shutil.which("expect"):
                return await self._run_remote_command_with_expect(
                    target=target,
                    command=command,
                    timeout=timeout,
                    env=env,
                )
            else:
                return (
                    "Error: Password SSH requires `sshpass` or `expect` to be installed on this machine.",
                    "error",
                )

        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        return await self._communicate_and_format(process=process, timeout=timeout)

    async def _run_remote_command_with_expect(
        self,
        *,
        target: ExecTarget,
        command: str,
        timeout: int,
        env: dict[str, str],
    ) -> tuple[str, str]:
        expect_env = env.copy()
        expect_env["NANOBOT_SSH_DEST"] = (
            f"{target.username}@{target.host}" if target.username else target.host
        )
        expect_env["NANOBOT_SSH_PORT"] = str(target.port)
        expect_env["NANOBOT_SSH_COMMAND"] = command
        expect_env["NANOBOT_SSH_TIMEOUT"] = str(timeout)
        script = self._build_expect_ssh_script()
        process = await asyncio.create_subprocess_exec(
            "expect",
            "-c",
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=expect_env,
        )
        result, status = await self._communicate_and_format(process=process, timeout=timeout)
        return self._strip_expect_transport_noise(result, target), status

    @staticmethod
    def _build_expect_ssh_script() -> str:
        """Build the expect script used for password-based SSH."""
        return r"""
set timeout $env(NANOBOT_SSH_TIMEOUT)
set password $env(NANOBOT_SSH_PASSWORD)
spawn ssh -p $env(NANOBOT_SSH_PORT) $env(NANOBOT_SSH_DEST) $env(NANOBOT_SSH_COMMAND)
expect {
    -re ".*yes/no.*" { send "yes\r"; exp_continue }
    -re ".*\[Pp\]assword:.*" { send "$password\r"; exp_continue }
    eof
}
catch wait result
set exit_code [lindex $result 3]
exit $exit_code
""".strip()

    @staticmethod
    def _strip_expect_transport_noise(result: str, target: ExecTarget) -> str:
        """Remove expect/ssh prompt noise from password-SSH results."""
        cleaned = result.replace("\r", "")
        destination = f"{target.username}@{target.host}" if target.username else target.host
        prompt_pattern = rf"^{re.escape(destination)}'s password:\s*$"
        closed_pattern = rf"^Connection to {re.escape(target.host)} closed by remote host\.\s*$"
        lines = []
        for line in cleaned.splitlines():
            stripped = line.strip()
            if not stripped:
                lines.append("")
                continue
            if stripped.startswith("spawn ssh "):
                continue
            if re.match(prompt_pattern, stripped):
                continue
            if re.match(closed_pattern, stripped):
                continue
            lines.append(line)

        compact = "\n".join(lines).strip()
        return compact or "(no output)"

    def _should_prompt_for_ssh_password(
        self,
        *,
        target: ExecTarget,
        status: str,
        result: str,
        ssh_password: str | None,
    ) -> bool:
        """Return True when CLI should ask for an SSH password and retry once."""
        if target.kind != "ssh":
            return False
        if ssh_password:
            return False
        if self._context_channel != "cli":
            return False
        if self._secret_prompt_callback is None:
            return False
        if status != "error":
            return False

        lower = result.lower()
        auth_markers = (
            "permission denied",
            "publickey,password",
            "publickey,gssapi",
            "password authentication failed",
            "keyboard-interactive",
            "can't open /dev/tty",
        )
        return any(marker in lower for marker in auth_markers)

    async def _prompt_for_ssh_password(self, target_label: str) -> str | None:
        """Request an SSH password via the configured CLI callback."""
        if self._secret_prompt_callback is None:
            return None
        return await self._secret_prompt_callback(target_label)

    async def _communicate_and_format(
        self,
        *,
        process: asyncio.subprocess.Process,
        timeout: int,
    ) -> tuple[str, str]:
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pass
            return f"Error: Command timed out after {timeout} seconds", "timeout"

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

        max_len = 10000
        if len(result) > max_len:
            result = result[:max_len] + f"\n... (truncated, {len(result) - max_len} more chars)"
        status = "ok" if process.returncode == 0 else "error"
        return result, status

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

    @staticmethod
    def _extract_absolute_paths(command: str) -> list[str]:
        """Compatibility wrapper kept for existing tests and callers."""
        return extract_absolute_paths(command)
