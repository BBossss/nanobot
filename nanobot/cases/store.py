"""Case record storage and index management."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from nanobot.utils.helpers import ensure_dir, safe_filename


class CaseStore:
    """Store case records as markdown files plus a lightweight JSON index."""

    _index_locks: dict[str, threading.Lock] = {}

    def __init__(self, workspace: Path, cases_path: str | None = None):
        self.workspace = workspace
        root = Path(cases_path).expanduser() if cases_path else workspace / "notes" / "cases"
        self.cases_dir = ensure_dir(root)
        self.index_file = self.cases_dir / "index.json"
        lock_key = str(self.index_file.resolve())
        self._index_lock = self._index_locks.setdefault(lock_key, threading.Lock())

    def next_case_id(self, now: datetime | None = None) -> str:
        now = now or datetime.now()
        day = now.strftime("%Y%m%d")
        prefix = f"INC-{day}-"
        max_num = 0
        for item in self._load_index()["cases"]:
            cid = item.get("id", "")
            if cid.startswith(prefix):
                tail = cid.split("-")[-1]
                if tail.isdigit():
                    max_num = max(max_num, int(tail))
        return f"{prefix}{max_num + 1:03d}"

    def write_case(
        self,
        *,
        title: str,
        trigger: str,
        source: str,
        summary: str,
        evidence: str,
        conclusion: str,
        suggestion: str,
        status: str = "open",
        host: str = "",
        service: str = "",
        severity: str = "medium",
        tags: list[str] | None = None,
        case_id: str | None = None,
        created_at: datetime | None = None,
        import_source: str = "",
    ) -> dict[str, Any]:
        now = created_at or datetime.now()
        case_id = case_id or self.next_case_id(now)
        created = now.isoformat(timespec="seconds")
        tags = tags or []
        slug = safe_filename((title or "case").lower().replace(" ", "-"))[:60] or "case"
        path = self.cases_dir / f"{case_id}-{slug}.md"

        frontmatter = [
            "---",
            f"id: {case_id}",
            f"title: {title}",
            f"source: {source}",
            f"created_at: {created}",
            f"trigger: {trigger}",
            f"host: {host}",
            f"service: {service}",
            f"severity: {severity}",
            f"status: {status}",
            "root_cause: pending",
            "tags:",
        ]
        if tags:
            frontmatter.extend([f"  - {t}" for t in tags])
        else:
            frontmatter.append("  - troubleshooting")
        if import_source:
            frontmatter.append(f"import_source: {import_source}")
        frontmatter.append("---")

        body = [
            "# Problem",
            summary or "(empty)",
            "",
            "# Evidence",
            evidence or "(empty)",
            "",
            "# Conclusion",
            conclusion or "(empty)",
            "",
            "# Suggestion",
            suggestion or "(empty)",
            "",
        ]
        content = "\n".join(frontmatter + [""] + body)
        path.write_text(content, encoding="utf-8")

        item = {
            "id": case_id,
            "title": title,
            "path": self._serialize_case_path(path),
            "source": source,
            "created_at": created,
            "trigger": trigger,
            "summary": summary[:300],
            "host": host,
            "service": service,
            "severity": severity,
            "status": status,
            "tags": tags or ["troubleshooting"],
        }
        self._upsert_index(item)
        return item

    def list_cases(self, limit: int = 20) -> list[dict[str, Any]]:
        cases = sorted(self._load_index()["cases"], key=lambda x: x.get("created_at", ""), reverse=True)
        return cases[: max(1, limit)]

    def search_cases(
        self,
        *,
        keyword: str = "",
        tag: str = "",
        host: str = "",
        service: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search case index by lightweight metadata fields."""
        keyword_l = keyword.strip().lower()
        tag_l = tag.strip().lower()
        host_l = host.strip().lower()
        service_l = service.strip().lower()

        matched: list[dict[str, Any]] = []
        for item in self._load_index()["cases"]:
            title = str(item.get("title", "")).lower()
            summary = str(item.get("summary", "")).lower()
            item_host = str(item.get("host", "")).lower()
            item_service = str(item.get("service", "")).lower()
            tags = [str(t).lower() for t in item.get("tags", []) if isinstance(t, str)]

            if keyword_l and keyword_l not in title and keyword_l not in summary:
                continue
            if tag_l and tag_l not in tags:
                continue
            if host_l and host_l not in item_host:
                continue
            if service_l and service_l not in item_service:
                continue
            matched.append(item)

        matched.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return matched[: max(1, limit)]

    def get_case(self, case_id: str) -> tuple[dict[str, Any] | None, str | None]:
        for item in self._load_index()["cases"]:
            if item.get("id") == case_id:
                case_file = self._resolve_case_path(item["path"])
                if not case_file.exists():
                    return item, None
                return item, case_file.read_text(encoding="utf-8")
        return None, None

    def _load_index(self) -> dict[str, Any]:
        if self.index_file.exists():
            try:
                data = json.loads(self.index_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("cases"), list):
                    return data
            except Exception:
                pass
        return {"version": 1, "cases": []}

    def _save_index(self, data: dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        tmp = self.index_file.with_name(f"{self.index_file.name}.tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(self.index_file)

    def _upsert_index(self, item: dict[str, Any]) -> None:
        with self._index_lock:
            data = self._load_index()
            cases = data["cases"]
            for i, old in enumerate(cases):
                if old.get("id") == item["id"]:
                    cases[i] = item
                    self._save_index(data)
                    return
            cases.append(item)
            self._save_index(data)

    def _serialize_case_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.workspace))
        except ValueError:
            return str(path)

    def _resolve_case_path(self, raw_path: str) -> Path:
        path = Path(raw_path).expanduser()
        if path.is_absolute():
            return path
        return self.workspace / path
