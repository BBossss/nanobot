"""Planning tool for structured troubleshooting execution plans."""

from __future__ import annotations

from typing import Any

from nanobot.agent.tools.base import Tool


class PlanningTool(Tool):
    """Generate a structured plan before execution."""

    @property
    def name(self) -> str:
        return "plan"

    @property
    def description(self) -> str:
        return "Generate a step-by-step troubleshooting plan with checkpoints."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "Troubleshooting goal"},
                "context": {"type": "string", "description": "Optional environment context"},
                "constraints": {
                    "type": "array",
                    "description": "Optional constraints, such as readonly or timebox",
                    "items": {"type": "string"},
                },
                "horizon": {
                    "type": "string",
                    "enum": ["quick", "full"],
                    "description": "Plan depth. quick=3 steps, full=6 steps",
                },
            },
            "required": ["goal"],
        }

    async def execute(
        self,
        goal: str,
        context: str = "",
        constraints: list[str] | None = None,
        horizon: str = "full",
        **kwargs: Any,
    ) -> str:
        constraints = constraints or []
        depth = 3 if horizon == "quick" else 6

        steps = [
            "Clarify symptoms and affected scope (host/service/time window).",
            "Collect readonly evidence (logs, metrics, system status).",
            "Correlate anomalies and form 1-2 likely root-cause hypotheses.",
            "Design validation checks to confirm or reject each hypothesis.",
            "Draft mitigation/workaround actions with risk and rollback notes.",
            "Produce a concise conclusion and next-step recommendation.",
        ][:depth]

        lines = [
            "# Troubleshooting Plan",
            f"- Goal: {goal.strip()}",
            f"- Horizon: {horizon}",
            f"- Context: {context.strip() or '(none)'}",
            "- Constraints:",
        ]
        if constraints:
            lines.extend([f"  - {c}" for c in constraints])
        else:
            lines.append("  - (none)")

        lines += ["", "## Execution Steps"]
        for i, s in enumerate(steps, start=1):
            lines.append(f"{i}. {s}")

        lines += [
            "",
            "## Checkpoints",
            "- Stop if data is insufficient; request missing logs/permissions.",
            "- Keep only confirmed facts in the final conclusion.",
        ]
        return "\n".join(lines)
