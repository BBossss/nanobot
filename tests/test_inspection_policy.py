from datetime import datetime

from nanobot.policies.inspection import InspectionPolicy


def test_inspection_policy_keywords_default() -> None:
    keywords = InspectionPolicy.keywords_for([])
    assert "error" in keywords
    assert "timeout" in keywords


def test_inspection_policy_should_generate_case() -> None:
    assert InspectionPolicy.should_generate_case(mode="always", has_findings=False) is True
    assert InspectionPolicy.should_generate_case(mode="error", has_findings=True) is True
    assert InspectionPolicy.should_generate_case(mode="error", has_findings=False) is False
    assert InspectionPolicy.should_generate_case(mode="never", has_findings=True) is False


def test_inspection_policy_build_case_draft() -> None:
    started = datetime(2026, 3, 8, 10, 30, 0)
    draft = InspectionPolicy.build_case_draft(
        started=started,
        trigger="cron",
        findings=[{"line": "ERROR storage failed"}],
        target_errors=["log: timeout"],
        report_path="/tmp/report.md",
        llm_summary="概览\n发现异常",
    )
    assert draft.title == "Inspection report 2026-03-08 10:30"
    assert draft.trigger == "cron"
    assert draft.status == "open"
    assert draft.severity == "high"
    assert "ERROR storage failed" in draft.evidence


def test_inspection_policy_render_report() -> None:
    started = datetime(2026, 3, 8, 10, 30, 0)
    report = InspectionPolicy.render_report(
        started=started,
        trigger="manual",
        target_results=[{"name": "main-log", "kind": "log_file", "matches": [{"line_no": 1}], "error": ""}],
        findings=[{"target": "main-log", "line_no": 12, "line": "ERROR timeout"}],
        target_errors=[],
        llm_summary="概览\n重点异常",
    )
    assert "# Inspection Report" in report
    assert "## Model Analysis" in report
    assert "ERROR timeout" in report
