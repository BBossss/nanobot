"""Inspection service for scheduled or manual troubleshooting scans."""

from __future__ import annotations

import asyncio
import shlex
from datetime import datetime
from pathlib import Path
from typing import Any

from nanobot.cases.store import CaseStore
from nanobot.config.schema import CasesConfig, InspectionConfig, InspectionTargetConfig
from nanobot.providers.base import LLMProvider
from nanobot.utils.helpers import ensure_dir


DEFAULT_KEYWORDS = (
    "error",
    "failed",
    "failure",
    "panic",
    "critical",
    "exception",
    "timeout",
)


class InspectionService:
    """Collect diagnostics signals and produce a markdown report."""

    def __init__(
        self,
        *,
        workspace: Path,
        inspection: InspectionConfig,
        provider: LLMProvider | None = None,
        model: str | None = None,
        cases: CasesConfig | None = None,
    ):
        self.workspace = workspace
        self.config = inspection
        self.provider = provider
        self.model = model
        self._case_store = CaseStore(workspace, cases.path if cases else None)
        report_dir = Path(self.config.report_dir).expanduser()
        self.report_dir = ensure_dir(report_dir)

    async def run(self, *, trigger: str = "manual") -> dict[str, Any]:
        """Run one inspection cycle and persist a markdown report."""
        started = datetime.now()
        targets = [t for t in self.config.targets if t.enabled]
        if not self.config.enabled:
            return {"status": "disabled", "targets": 0, "findings": 0, "report_path": ""}

        target_results: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []
        target_errors: list[str] = []

        for target in targets:
            result = await self._collect_target(target)
            target_results.append(result)
            findings.extend(result.get("matches", []))
            if err := result.get("error"):
                target_errors.append(f"{target.name}: {err}")

        llm_summary = await self._analyze_with_llm(findings, target_results, target_errors)
        report = self._render_report(
            started=started,
            trigger=trigger,
            target_results=target_results,
            findings=findings,
            target_errors=target_errors,
            llm_summary=llm_summary,
        )

        report_path = self._report_path(started)
        report_path.write_text(report, encoding="utf-8")

        case_id = ""
        should_case = self._should_generate_case(bool(findings))
        if should_case:
            item = self._case_store.write_case(
                title=f"Inspection report {started.strftime('%Y-%m-%d %H:%M')}",
                trigger=trigger,
                source="inspection",
                summary=f"Inspection findings: {len(findings)}, target errors: {len(target_errors)}",
                evidence=f"Report path: {report_path}\n\n" + "\n".join(f["line"] for f in findings[:20]),
                conclusion=(llm_summary or "Please review report details.").strip()[:3000],
                suggestion="Prioritize high-frequency errors and verify affected components.",
                status="open" if findings else "resolved",
                severity="high" if findings else "low",
                tags=["inspection", "auto"],
            )
            case_id = item["id"]

        return {
            "status": "ok",
            "targets": len(targets),
            "findings": len(findings),
            "target_errors": len(target_errors),
            "report_path": str(report_path),
            "case_id": case_id,
        }

    async def _collect_target(self, target: InspectionTargetConfig) -> dict[str, Any]:
        if target.kind == "log_file":
            return await self._collect_log_file(target)
        if target.kind == "journal":
            return await self._collect_journal(target)
        if target.kind == "command":
            return await self._collect_command(target)
        return {"name": target.name, "kind": target.kind, "matches": [], "error": "unsupported target kind"}

    async def _collect_log_file(self, target: InspectionTargetConfig) -> dict[str, Any]:
        path = Path(target.path).expanduser()
        if not path.exists():
            return {"name": target.name, "kind": target.kind, "matches": [], "error": f"log file not found: {path}"}
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()[-max(1, target.max_lines):]
        return {
            "name": target.name,
            "kind": target.kind,
            "matches": self._filter_lines(lines, target),
            "error": "",
        }

    async def _collect_journal(self, target: InspectionTargetConfig) -> dict[str, Any]:
        cmd = ["journalctl", "-n", str(max(1, target.max_lines)), "--no-pager"]
        if target.unit:
            cmd += ["-u", target.unit]
        out, err = await self._run_cmd(cmd)
        if err:
            return {"name": target.name, "kind": target.kind, "matches": [], "error": err}
        return {
            "name": target.name,
            "kind": target.kind,
            "matches": self._filter_lines(out.splitlines(), target),
            "error": "",
        }

    async def _collect_command(self, target: InspectionTargetConfig) -> dict[str, Any]:
        if not target.command.strip():
            return {"name": target.name, "kind": target.kind, "matches": [], "error": "empty command"}
        out, err = await self._run_cmd(shlex.split(target.command))
        if err:
            return {"name": target.name, "kind": target.kind, "matches": [], "error": err}
        lines = out.splitlines()[-max(1, target.max_lines):]
        return {
            "name": target.name,
            "kind": target.kind,
            "matches": self._filter_lines(lines, target),
            "error": "",
        }

    async def _run_cmd(self, cmd: list[str], timeout: int = 20) -> tuple[str, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")
            if proc.returncode != 0:
                return stdout, (stderr.strip() or f"command failed with exit code {proc.returncode}")
            return stdout, ""
        except FileNotFoundError:
            return "", f"command not found: {cmd[0]}"
        except asyncio.TimeoutError:
            return "", f"command timeout after {timeout}s"
        except Exception as e:  # pragma: no cover - unexpected runtime errors
            return "", str(e)

    def _filter_lines(self, lines: list[str], target: InspectionTargetConfig) -> list[dict[str, Any]]:
        keywords = [k.lower() for k in (target.keywords or list(DEFAULT_KEYWORDS)) if k]
        matches: list[dict[str, Any]] = []
        max_matches = max(1, target.max_matches)

        for idx, line in enumerate(lines, start=1):
            line_l = line.lower()
            if keywords and not any(kw in line_l for kw in keywords):
                continue
            matches.append({"line_no": idx, "line": line, "target": target.name})
            if len(matches) >= max_matches:
                break
        return matches

    async def _analyze_with_llm(
        self,
        findings: list[dict[str, Any]],
        target_results: list[dict[str, Any]],
        target_errors: list[str],
    ) -> str:
        if not self.provider or not self.model:
            return ""
        if not findings and not target_errors:
            return ""

        finding_text = "\n".join(
            f"- [{f['target']}:{f['line_no']}] {f['line'][:240]}" for f in findings[:80]
        )
        target_text = "\n".join(
            f"- {r.get('name', '')} ({r.get('kind', '')}): {len(r.get('matches', []))} matches"
            for r in target_results
        )
        error_text = "\n".join(f"- {e}" for e in target_errors) or "- none"
        prompt = (
            "You are an SRE assistant. Summarize inspection findings in Chinese.\n"
            "Use sections: 概览, 重点异常, 可能原因, 建议动作.\n\n"
            f"Targets:\n{target_text}\n\n"
            f"Collector errors:\n{error_text}\n\n"
            f"Matched lines:\n{finding_text or '- none'}"
        )

        try:
            resp = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=1200,
                temperature=0.1,
            )
            return (resp.content or "").strip()
        except Exception:
            return ""

    def _render_report(
        self,
        *,
        started: datetime,
        trigger: str,
        target_results: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        target_errors: list[str],
        llm_summary: str,
    ) -> str:
        lines = [
            f"# Inspection Report ({started.strftime('%Y-%m-%d %H:%M:%S')})",
            "",
            "## Summary",
            f"- Trigger: {trigger}",
            f"- Targets: {len(target_results)}",
            f"- Findings: {len(findings)}",
            f"- Target Errors: {len(target_errors)}",
            "",
            "## Target Overview",
        ]
        if target_results:
            for result in target_results:
                lines.append(
                    f"- {result.get('name', '')} [{result.get('kind', '')}] "
                    f"matches={len(result.get('matches', []))}"
                )
                if result.get("error"):
                    lines.append(f"  collector_error: {result['error']}")
        else:
            lines.append("- No targets configured")

        lines += ["", "## Matched Lines"]
        if findings:
            for f in findings[:200]:
                lines.append(f"- [{f['target']}:{f['line_no']}] {f['line']}")
        else:
            lines.append("- No matched lines")

        lines += ["", "## Collector Errors"]
        if target_errors:
            for e in target_errors:
                lines.append(f"- {e}")
        else:
            lines.append("- None")

        lines += ["", "## Model Analysis"]
        lines.append(llm_summary or "Model analysis unavailable or skipped.")
        lines.append("")
        return "\n".join(lines)

    def _report_path(self, now: datetime) -> Path:
        day_dir = ensure_dir(self.report_dir / now.strftime("%Y%m%d"))
        return day_dir / f"inspection-{now.strftime('%H%M%S')}.md"

    def _should_generate_case(self, has_findings: bool) -> bool:
        mode = self.config.generate_case_on
        if mode == "always":
            return True
        if mode == "error":
            return has_findings
        return False
