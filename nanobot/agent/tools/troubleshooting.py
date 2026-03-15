"""Target-aware troubleshooting tools (stub implementations)."""

from __future__ import annotations

from typing import Any

from nanobot.agent.tools.base import Tool


class _BaseTroubleshootingTool(Tool):
    """Shared stub for troubleshooting tools."""

    async def execute(self, **kwargs: Any) -> str:
        return "Error: Tool not implemented yet."


class FindLogsTool(_BaseTroubleshootingTool):
    def __init__(self, *, allowed_log_roots: list[str] | None = None, max_results: int = 20):
        self.allowed_log_roots = allowed_log_roots or []
        self.max_results = max_results

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


class ReadLogTailTool(_BaseTroubleshootingTool):
    def __init__(self, *, default_lines: int = 200, max_lines: int = 2000):
        self.default_lines = default_lines
        self.max_lines = max_lines

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


class SearchLogTool(_BaseTroubleshootingTool):
    def __init__(self, *, max_hits: int = 100):
        self.max_hits = max_hits

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


class ServiceStatusTool(_BaseTroubleshootingTool):
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


class ProcessSnapshotTool(_BaseTroubleshootingTool):
    def __init__(self, *, max_processes: int = 20):
        self.max_processes = max_processes

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
