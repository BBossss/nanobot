"""Tools for querying troubleshooting case records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.cases.store import CaseStore


class SearchCasesTool(Tool):
    """Search case index by metadata fields."""

    def __init__(self, workspace: Path, cases_path: str | None = None):
        self._store = CaseStore(workspace=workspace, cases_path=cases_path)

    @property
    def name(self) -> str:
        return "search_cases"

    @property
    def description(self) -> str:
        return "Search troubleshooting cases by keyword/tag/host/service."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
                "tag": {"type": "string"},
                "host": {"type": "string"},
                "service": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
        }

    async def execute(
        self,
        keyword: str = "",
        tag: str = "",
        host: str = "",
        service: str = "",
        limit: int = 10,
        **kwargs: Any,
    ) -> str:
        rows = self._store.search_cases(
            keyword=keyword,
            tag=tag,
            host=host,
            service=service,
            limit=limit,
        )
        if not rows:
            return "No cases found."

        lines = [f"Found {len(rows)} case(s):"]
        for row in rows:
            lines.append(
                f"- {row.get('id', '')} | {row.get('title', '')} | "
                f"host={row.get('host', '')} service={row.get('service', '')} "
                f"tags={','.join([str(t) for t in row.get('tags', [])])}"
            )
        return "\n".join(lines)


class GetCaseTool(Tool):
    """Read full case content by ID."""

    def __init__(self, workspace: Path, cases_path: str | None = None):
        self._store = CaseStore(workspace=workspace, cases_path=cases_path)

    @property
    def name(self) -> str:
        return "get_case"

    @property
    def description(self) -> str:
        return "Get a full troubleshooting case by case ID."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "case_id": {"type": "string"},
            },
            "required": ["case_id"],
        }

    async def execute(self, case_id: str, **kwargs: Any) -> str:
        item, content = self._store.get_case(case_id)
        if not item:
            return f"Case not found: {case_id}"
        if not content:
            return f"Case file missing for {case_id}"
        return content[:10000]
