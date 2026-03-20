import pytest
from types import SimpleNamespace

from nanobot.agent.workflow import result_policy as workflow_result_policy


def _assert_classification(*, user_content: str, final_content: str, expected_kind: str) -> None:
    assert (
        workflow_result_policy.classify_output_kind(
            user_content=user_content,
            final_content=final_content,
            messages=None,
        )
        == expected_kind
    )


def test_classification_returns_troubleshooting_reply_for_natural_language_conclusion() -> None:
    _assert_classification(
        user_content="帮我判断这个服务为什么报错",
        final_content="已确认事实：日志里连续出现连接超时。根因已确认就是数据库连接池耗尽。",
        expected_kind="troubleshooting_reply",
    )


def test_classification_returns_inspection_artifact_for_structured_inspection_body() -> None:
    _assert_classification(
        user_content="把这轮检查整理成 inspection",
        final_content="# Inspection\n- [target] node-a\n- [summary] nginx active",
        expected_kind="inspection_artifact",
    )


def test_classification_does_not_use_incidental_body_text_to_pick_artifact_kind() -> None:
    _assert_classification(
        user_content="输出 report artifact",
        final_content="Summary: customer mentioned the word case in chat\nEvidence: timeout seen in logs",
        expected_kind="report_artifact",
    )


def test_classification_uses_structured_body_path_for_inspection_frontmatter() -> None:
    _assert_classification(
        user_content="把这轮检查整理成 inspection artifact",
        final_content="---\ntitle: node-a readonly snapshot\nowner: nanobot\n---\nSummary: nginx active",
        expected_kind="inspection_artifact",
    )


def test_classification_keeps_frontmatter_wrapped_troubleshooting_reply_as_troubleshooting() -> None:
    _assert_classification(
        user_content="帮我判断这个服务为什么报错",
        final_content=(
            "---\nowner: nanobot\nsource: readonly-check\n---\n"
            "已确认事实：日志里连续出现连接超时。当前倾向：数据库连接池耗尽。"
        ),
        expected_kind="troubleshooting_reply",
    )


def test_classification_returns_report_artifact_for_structured_report_body() -> None:
    _assert_classification(
        user_content="输出 report",
        final_content="# Report\nSummary: service unhealthy\nEvidence: timeout seen in logs",
        expected_kind="report_artifact",
    )


def test_classification_returns_report_artifact_for_plain_markdown_inspection_report_heading() -> None:
    _assert_classification(
        user_content="输出 inspection report",
        final_content="# Inspection report\n\n## Evidence\n- node-a logrotate failed",
        expected_kind="report_artifact",
    )


def test_classification_returns_report_artifact_for_inspection_report_frontmatter_type() -> None:
    _assert_classification(
        user_content="输出 inspection report",
        final_content="---\ntype: inspection_report\ncase_id: INC-20260319-001\n---\nSummary: service unhealthy",
        expected_kind="report_artifact",
    )


def test_classification_uses_structured_body_path_for_report_key_value_body() -> None:
    _assert_classification(
        user_content="输出这次故障的 report artifact",
        final_content="Summary: service unhealthy\nEvidence: timeout seen in logs\nImpact: write path blocked",
        expected_kind="report_artifact",
    )


def test_classification_returns_case_artifact_for_structured_case_body() -> None:
    _assert_classification(
        user_content="导出 case",
        final_content="# Case\nCase ID: CASE-001\nStatus: open",
        expected_kind="case_artifact",
    )


def test_classification_uses_structured_body_path_for_case_key_value_body() -> None:
    _assert_classification(
        user_content="导出这个事件的 case artifact",
        final_content="Title: storage incident\nStatus: open\nOwner: ops-oncall",
        expected_kind="case_artifact",
    )


def test_classification_returns_generic_reply_for_unrelated_plain_reply() -> None:
    _assert_classification(
        user_content="今天天气怎么样",
        final_content="我现在只能帮你处理排障相关的事情。",
        expected_kind="generic_reply",
    )


def test_classification_does_not_treat_timeline_like_content_without_valid_event_body_as_timeline_artifact() -> None:
    _assert_classification(
        user_content="整理一下这次故障时间线",
        final_content="# Timeline\n- 10:00 服务启动\n- 10:05 指标抖动\n- 10:08 恢复",
        expected_kind="generic_reply",
    )


def test_classification_returns_timeline_artifact_for_canonical_markdown_timeline_body() -> None:
    _assert_classification(
        user_content="整理一下这次故障时间线",
        final_content=(
            "# Timeline\n"
            "## Events\n"
            "- Timestamp: 2026-03-20 10:00\n"
            "  Event: service started\n"
            "  Evidence: boot log entries\n"
            "- Timestamp: 2026-03-20 10:05\n"
            "  Event: timeout spike\n"
            "  Evidence: repeated 504s in logs\n"
        ),
        expected_kind="timeline_artifact",
    )


def test_classification_returns_timeline_artifact_for_canonical_timeline_body_with_optional_target_and_source() -> None:
    _assert_classification(
        user_content="整理一下这次故障时间线",
        final_content=(
            "# Timeline\n"
            "## Events\n"
            "- Timestamp: 2026-03-20 10:00\n"
            "  Event: service started\n"
            "  Evidence: boot log entries\n"
            "  Target: node-a\n"
            "  Source: /var/log/service.log:12\n"
            "- Timestamp: 2026-03-20 10:05\n"
            "  Event: timeout spike\n"
            "  Evidence: repeated 504s in logs\n"
            "  Target: node-b\n"
            "  Source: /var/log/service.log:48\n"
        ),
        expected_kind="timeline_artifact",
    )


def test_classification_returns_timeline_artifact_for_frontmatter_marked_timeline_body() -> None:
    _assert_classification(
        user_content="整理成 timeline artifact",
        final_content=(
            "---\nkind: timeline\n---\n"
            "# Timeline\n"
            "## Events\n"
            "- Timestamp: 2026-03-20 10:00\n"
            "  Event: service started\n"
            "  Evidence: boot log entries\n"
            "- Timestamp: 2026-03-20 10:05\n"
            "  Event: timeout spike\n"
            "  Evidence: repeated 504s in logs\n"
        ),
        expected_kind="timeline_artifact",
    )


def test_classification_returns_timeline_artifact_for_frontmatter_only_marker_timeline_body() -> None:
    _assert_classification(
        user_content="整理成 timeline artifact",
        final_content=(
            "---\nkind: timeline\n---\n"
            "## Events\n"
            "- Timestamp: 2026-03-20 10:00\n"
            "  Event: service started\n"
            "  Evidence: boot log entries\n"
            "  Target: node-a\n"
            "  Source: /var/log/service.log:12\n"
        ),
        expected_kind="timeline_artifact",
    )


def test_classification_does_not_treat_malformed_timeline_heading_without_valid_events_as_timeline_artifact() -> None:
    _assert_classification(
        user_content="整理一下这次故障时间线",
        final_content=(
            "# Timeline\n"
            "## Events\n"
            "- service started\n"
            "- timeout spike\n"
            "- recovery\n"
        ),
        expected_kind="generic_reply",
    )


def test_classification_does_not_treat_frontmatter_timeline_marker_with_invalid_body_as_timeline_artifact() -> None:
    _assert_classification(
        user_content="整理成 timeline artifact",
        final_content=(
            "---\nkind: timeline\n---\n"
            "# Timeline\n"
            "## Events\n"
            "- service started\n"
            "- timeout spike\n"
        ),
        expected_kind="generic_reply",
    )


def test_classification_does_not_treat_timestamp_mentions_in_troubleshooting_reply_as_timeline_artifact() -> None:
    _assert_classification(
        user_content="帮我判断这个服务为什么报错",
        final_content=(
            "- 10:05 看到 timeout\n"
            "- 10:07 再次重试失败\n"
            "当前倾向：数据库连接池耗尽。"
        ),
        expected_kind="troubleshooting_reply",
    )


def test_classification_does_not_treat_timestamp_event_evidence_body_without_explicit_timeline_marker_as_timeline_artifact() -> None:
    _assert_classification(
        user_content="输出 artifact",
        final_content=(
            "Timestamp: 2026-03-20 10:00\n"
            "Event: service started\n"
            "Evidence: boot log entries\n"
        ),
        expected_kind="generic_reply",
    )


def test_classification_does_not_treat_timestamped_troubleshooting_summary_as_timeline() -> None:
    _assert_classification(
        user_content="帮我判断这个服务为什么报错",
        final_content="- 10:05 看到 timeout\n- 10:07 再次重试失败\n当前倾向：数据库连接池耗尽。",
        expected_kind="troubleshooting_reply",
    )


def test_classification_does_not_treat_explicit_output_kind_timeline_marker_with_invalid_body_as_timeline_artifact() -> None:
    _assert_classification(
        user_content="整理成 timeline artifact",
        final_content="---\noutput_kind: timeline\nscope: readonly\n---\nEvent: 10:05 timeout spike",
        expected_kind="generic_reply",
    )


def test_classification_recognizes_quoted_frontmatter_report_kind() -> None:
    _assert_classification(
        user_content="输出 artifact",
        final_content='---\nkind: "report"\nowner: nanobot\n---\nSummary: service unhealthy',
        expected_kind="report_artifact",
    )


def test_classification_does_not_treat_single_quoted_frontmatter_timeline_output_kind_with_invalid_body_as_timeline_artifact() -> None:
    _assert_classification(
        user_content="输出 artifact",
        final_content="---\noutput_kind: 'timeline'\nscope: readonly\n---\nEvent: timeout spike",
        expected_kind="generic_reply",
    )


def test_classification_returns_root_cause_candidate_for_candidate_like_content() -> None:
    _assert_classification(
        user_content="给我一个 root cause candidate",
        final_content="# Root Cause Candidate\nCandidate: 数据库连接池耗尽\nConfidence: medium",
        expected_kind="root_cause_candidate",
    )


def test_classification_keeps_unlabeled_candidate_block_as_troubleshooting_reply() -> None:
    _assert_classification(
        user_content="帮我判断这个服务为什么报错",
        final_content=(
            "Candidate: 数据库连接池耗尽\n"
            "Confidence: medium\n"
            "Evidence: timeout burst\n"
            "当前倾向：数据库连接池耗尽。"
        ),
        expected_kind="troubleshooting_reply",
    )


def test_classification_recognizes_hyphenated_root_cause_candidate_heading() -> None:
    _assert_classification(
        user_content="输出 artifact",
        final_content="# Root-Cause Candidate\nCandidate: 数据库连接池耗尽\nConfidence: medium\nEvidence: timeout burst",
        expected_kind="root_cause_candidate",
    )


def test_classification_uses_structured_body_path_for_root_cause_candidate_key_values() -> None:
    _assert_classification(
        user_content="给我一个 root cause candidate artifact",
        final_content="Candidate: 数据库连接池耗尽\nConfidence: medium\nEvidence: timeout burst",
        expected_kind="root_cause_candidate",
    )


def test_classification_does_not_treat_generic_candidate_heading_as_root_cause_candidate() -> None:
    _assert_classification(
        user_content="给个普通候选项列表",
        final_content="# Candidate\nOption: retry deploy\nStatus: pending",
        expected_kind="generic_reply",
    )


def test_timeline_artifact_is_not_a_troubleshooting_rewrite_candidate() -> None:
    assert (
        workflow_result_policy.is_troubleshooting_result_candidate(
            "# Timeline\n- 10:00 服务启动\n- 10:05 指标抖动\n- 10:08 恢复"
        )
        is False
    )


def test_root_cause_candidate_artifact_is_not_a_troubleshooting_rewrite_candidate() -> None:
    assert (
        workflow_result_policy.is_troubleshooting_result_candidate(
            "# Root Cause Candidate\nCandidate: 数据库连接池耗尽\nConfidence: medium\nEvidence: timeout burst"
        )
        is False
    )


def test_timestamp_event_key_values_stay_troubleshooting_reply_without_explicit_timeline_marker() -> None:
    _assert_classification(
        user_content="帮我判断这个服务为什么报错",
        final_content=(
            "Timestamp: 10:05\n"
            "Event: timeout spike\n"
            "已确认事实：同一时间段请求连续失败。\n"
            "当前倾向：数据库连接池耗尽。"
        ),
        expected_kind="troubleshooting_reply",
    )


def test_frontmatter_wrapped_troubleshooting_reply_stays_rewrite_eligible() -> None:
    assert (
        workflow_result_policy.is_troubleshooting_result_candidate(
            "---\nowner: nanobot\nsource: readonly-check\n---\n"
            "已确认事实：日志里连续出现连接超时。当前倾向：数据库连接池耗尽。"
        )
        is True
    )


def test_evidence_first_still_rewrites_frontmatter_wrapped_troubleshooting_reply() -> None:
    session = SimpleNamespace(metadata={"workflow_result_mode": "evidence_first"})

    shaped = workflow_result_policy.shape_evidence_first_result(
        session=session,
        user_content="帮我判断这个服务为什么报错",
        final_content=(
            "---\nowner: nanobot\nsource: readonly-check\n---\n"
            "已确认事实：日志里连续出现连接超时。当前倾向：数据库连接池耗尽。"
        ),
        messages=None,
    )

    assert shaped is not None
    assert "当前倾向" in shaped
    assert "不确定点" in shaped


def test_shape_evidence_first_result_leaves_canonical_timeline_body_unchanged_byte_for_byte() -> None:
    session = SimpleNamespace(metadata={"workflow_result_mode": "evidence_first"})
    final_content = (
        "# Timeline\n"
        "## Events\n"
        "- Timestamp: 2026-03-20 10:00\n"
        "  Event: service started\n"
        "  Evidence: boot log entries\n"
        "- Timestamp: 2026-03-20 10:05\n"
        "  Event: timeout spike\n"
        "  Evidence: repeated 504s in logs\n"
    )

    shaped = workflow_result_policy.shape_evidence_first_result(
        session=session,
        user_content="整理一下这次故障时间线",
        final_content=final_content,
        messages=None,
    )

    assert shaped == final_content


def test_shape_evidence_first_result_leaves_canonical_timeline_body_with_optional_target_and_source_unchanged_byte_for_byte() -> None:
    session = SimpleNamespace(metadata={"workflow_result_mode": "evidence_first"})
    final_content = (
        "# Timeline\n"
        "## Events\n"
        "- Timestamp: 2026-03-20 10:00\n"
        "  Event: service started\n"
        "  Evidence: boot log entries\n"
        "  Target: node-a\n"
        "  Source: /var/log/service.log:12\n"
        "- Timestamp: 2026-03-20 10:05\n"
        "  Event: timeout spike\n"
        "  Evidence: repeated 504s in logs\n"
        "  Target: node-b\n"
        "  Source: /var/log/service.log:48\n"
    )

    shaped = workflow_result_policy.shape_evidence_first_result(
        session=session,
        user_content="整理一下这次故障时间线",
        final_content=final_content,
        messages=None,
    )

    assert shaped == final_content


@pytest.mark.parametrize(
    ("user_content", "final_content"),
    [
        (
            "帮我判断这个服务为什么报错",
            "已确认事实：日志里连续出现连接超时。当前倾向：数据库连接池耗尽。",
        ),
        (
            "把这轮检查整理成 inspection",
            "# Inspection\n- [target] node-a\n- [summary] nginx active",
        ),
        (
            "输出 report artifact",
            "# Report\nSummary: service unhealthy\nEvidence: timeout seen in logs",
        ),
        (
            "导出这个事件的 case artifact",
            "# Case\nCase ID: CASE-001\nStatus: open",
        ),
        (
            "整理一下这次故障时间线",
            "# Timeline\n- 10:00 服务启动\n- 10:05 开始报错\n- 10:08 恢复",
        ),
        (
            "给我一个 root cause candidate",
            "# Root Cause Candidate\nCandidate: 数据库连接池耗尽\nConfidence: medium",
        ),
        (
            "今天天气怎么样",
            "我现在只能帮你处理排障相关的事情。",
        ),
    ],
)
def test_candidate_eligibility_matches_output_kind_when_user_content_is_present(
    user_content: str,
    final_content: str,
) -> None:
    classified_kind = workflow_result_policy.classify_output_kind(
        user_content=user_content,
        final_content=final_content,
        messages=None,
    )
    expected = classified_kind == "troubleshooting_reply"

    assert (
        workflow_result_policy.is_troubleshooting_result_candidate(
            final_content,
            user_content=user_content,
            messages=None,
        )
        is expected
    )


def test_candidate_eligibility_forwards_messages_when_user_content_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_messages = [{"role": "tool", "content": "evidence"}]
    captured: dict[str, object] = {}

    def fake_classify_output_kind(**kwargs: object) -> str:
        captured.update(kwargs)
        return workflow_result_policy.OUTPUT_KIND_TROUBLESHOOTING_REPLY

    monkeypatch.setattr(workflow_result_policy, "classify_output_kind", fake_classify_output_kind)

    assert (
        workflow_result_policy.is_troubleshooting_result_candidate(
            "已确认事实：日志里连续出现连接超时。当前倾向：数据库连接池耗尽。",
            user_content="帮我判断这个服务为什么报错",
            messages=session_messages,
        )
        is True
    )
    assert captured["messages"] is session_messages
    assert captured["user_content"] == "帮我判断这个服务为什么报错"


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (
            "已确认事实：日志里连续出现连接超时。当前倾向：数据库连接池耗尽。",
            True,
        ),
        (
            "# Inspection\n- [target] node-a\n- [summary] nginx active",
            False,
        ),
        (
            "# Report\nSummary: service unhealthy\nEvidence: timeout seen in logs",
            False,
        ),
        (
            "# Case\nCase ID: CASE-001\nStatus: open",
            False,
        ),
        (
            "# Timeline\n- 10:00 服务启动\n- 10:05 指标抖动\n- 10:08 恢复",
            False,
        ),
        (
            "# Root Cause Candidate\nCandidate: 数据库连接池耗尽\nConfidence: medium",
            False,
        ),
        (
            "我现在只能帮你处理排障相关的事情。",
            False,
        ),
    ],
)
def test_candidate_eligibility_fallback_without_user_content_is_conservative(
    content: str,
    expected: bool,
) -> None:
    assert workflow_result_policy.is_troubleshooting_result_candidate(content) is expected


def test_shape_evidence_first_result_dispatches_troubleshooting_reply_through_evidence_first_logic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SimpleNamespace(metadata={"workflow_result_mode": "evidence_first"})
    final_content = "已确认事实：日志里持续报错。根因已确认，就是日志轮转失败。"
    monkeypatch.setattr(
        workflow_result_policy,
        "classify_output_kind",
        lambda **_kwargs: workflow_result_policy.OUTPUT_KIND_TROUBLESHOOTING_REPLY,
    )

    shaped = workflow_result_policy.shape_evidence_first_result(
        session=session,
        user_content="帮我先判断一下结果",
        final_content=final_content,
        messages=None,
    )

    assert shaped is not None
    assert "当前倾向" in shaped
    assert "根因已确认" not in shaped
    assert "不确定点" in shaped


@pytest.mark.parametrize(
    ("kind", "final_content"),
    [
        (
            workflow_result_policy.OUTPUT_KIND_INSPECTION_ARTIFACT,
            "已确认事实：日志里持续报错。根因已确认，就是日志轮转失败。",
        ),
        (
            workflow_result_policy.OUTPUT_KIND_REPORT_ARTIFACT,
            "已确认事实：日志里持续报错。根因已确认，就是日志轮转失败。",
        ),
        (
            workflow_result_policy.OUTPUT_KIND_CASE_ARTIFACT,
            "已确认事实：日志里持续报错。根因已确认，就是日志轮转失败。",
        ),
        (
            workflow_result_policy.OUTPUT_KIND_TIMELINE_ARTIFACT,
            "已确认事实：日志里持续报错。根因已确认，就是日志轮转失败。",
        ),
        (
            workflow_result_policy.OUTPUT_KIND_ROOT_CAUSE_CANDIDATE,
            "已确认事实：日志里持续报错。根因已确认，就是日志轮转失败。",
        ),
        (
            workflow_result_policy.OUTPUT_KIND_GENERIC_REPLY,
            "已确认事实：日志里持续报错。根因已确认，就是日志轮转失败。",
        ),
    ],
)
def test_shape_evidence_first_result_dispatch_leaves_non_troubleshooting_kinds_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    final_content: str,
) -> None:
    session = SimpleNamespace(metadata={"workflow_result_mode": "evidence_first"})
    monkeypatch.setattr(
        workflow_result_policy,
        "classify_output_kind",
        lambda **_kwargs: kind,
    )

    shaped = workflow_result_policy.shape_evidence_first_result(
        session=session,
        user_content="帮我先判断一下结果",
        final_content=final_content,
        messages=None,
    )

    assert shaped == final_content


@pytest.mark.parametrize(
    "final_content",
    [
        "# Inspection report\n\n## Evidence\n- node-a logrotate failed\n\n## Conclusion\nPlease review report details.\n",
        (
            "---\n"
            "type: inspection_report\n"
            "case_id: INC-20260319-001\n"
            "---\n"
            "# Inspection report\n\n"
            "## Evidence\n"
            "- [node-a/log:42] logrotate failed\n\n"
            "## Conclusion\n"
            "Please review report details.\n"
        ),
    ],
)
def test_shape_evidence_first_result_leaves_inspection_report_variants_unchanged(
    final_content: str,
) -> None:
    session = SimpleNamespace(metadata={"workflow_result_mode": "evidence_first"})

    shaped = workflow_result_policy.shape_evidence_first_result(
        session=session,
        user_content="storage 集群出问题了",
        final_content=final_content,
        messages=None,
    )

    assert shaped == final_content
