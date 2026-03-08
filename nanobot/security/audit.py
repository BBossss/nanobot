"""Shared audit logging for command execution."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from nanobot.utils.helpers import ensure_dir


class CommandAuditLogger:
    """Append command execution audit events to workspace-local JSONL."""

    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace).expanduser()
        self.audit_dir = ensure_dir(self.workspace / "audit")
        self.audit_file = self.audit_dir / "commands.jsonl"

    def record(
        self,
        *,
        source: str,
        command: str,
        status: str,
        cwd: str,
        detail: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "source": source,
            "command": command,
            "status": status,
            "cwd": cwd,
            "detail": detail[:500],
            "metadata": metadata or {},
        }
        with self.audit_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
