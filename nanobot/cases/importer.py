"""Import existing troubleshooting records into CaseStore."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nanobot.cases.store import CaseStore


class CaseImporter:
    """Import markdown, text, and JSON cases."""

    def __init__(self, store: CaseStore):
        self.store = store

    def import_path(self, source_path: str) -> list[dict[str, Any]]:
        path = Path(source_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Import path not found: {source_path}")
        files: list[Path]
        if path.is_file():
            files = [path]
        else:
            files = [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in {".md", ".txt", ".json"}]
        imported: list[dict[str, Any]] = []
        for f in files:
            imported.extend(self._import_file(f))
        return imported

    def _import_file(self, path: Path) -> list[dict[str, Any]]:
        if path.suffix.lower() == ".json":
            return self._import_json(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        return [self.store.write_case(
            title=path.stem,
            trigger="import",
            source="imported",
            summary=text[:3000],
            evidence="Imported from existing document",
            conclusion="Pending manual review",
            suggestion="Review and normalize this imported case",
            tags=["imported"],
            import_source=str(path),
        )]

    def _import_json(self, path: Path) -> list[dict[str, Any]]:
        data = json.loads(path.read_text(encoding="utf-8"))
        items: list[dict[str, Any]]
        if isinstance(data, list):
            items = [i for i in data if isinstance(i, dict)]
        elif isinstance(data, dict):
            items = [data]
        else:
            return []
        imported: list[dict[str, Any]] = []
        for item in items:
            imported.append(self.store.write_case(
                title=str(item.get("title", path.stem)),
                trigger="import",
                source="imported",
                summary=str(item.get("summary", item.get("problem", "")))[:3000],
                evidence=str(item.get("evidence", "Imported JSON case"))[:3000],
                conclusion=str(item.get("conclusion", "Pending manual review"))[:3000],
                suggestion=str(item.get("suggestion", "Review and normalize this imported case"))[:3000],
                host=str(item.get("host", "")),
                service=str(item.get("service", "")),
                severity=str(item.get("severity", "medium")),
                status=str(item.get("status", "open")),
                tags=item.get("tags") if isinstance(item.get("tags"), list) else ["imported"],
                import_source=str(path),
            ))
        return imported
