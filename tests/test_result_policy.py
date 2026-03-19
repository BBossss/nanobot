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


def test_classification_returns_report_artifact_for_structured_report_body() -> None:
    _assert_classification(
        user_content="输出 report",
        final_content="# Report\nSummary: service unhealthy\nEvidence: timeout seen in logs",
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


def test_classification_returns_timeline_artifact_for_timeline_like_content() -> None:
    _assert_classification(
        user_content="整理一下这次故障时间线",
        final_content="# Timeline\n- 10:00 服务启动\n- 10:05 开始报错\n- 10:08 恢复",
        expected_kind="timeline_artifact",
    )


def test_classification_does_not_treat_timestamped_troubleshooting_summary_as_timeline() -> None:
    _assert_classification(
        user_content="帮我判断这个服务为什么报错",
        final_content="- 10:05 看到 timeout\n- 10:07 再次重试失败\n当前倾向：数据库连接池耗尽。",
        expected_kind="troubleshooting_reply",
    )


def test_classification_uses_structured_body_path_for_timeline_frontmatter() -> None:
    _assert_classification(
        user_content="整理成 timeline artifact",
        final_content="---\nowner: nanobot\nscope: readonly\n---\nEvent: 10:05 timeout spike",
        expected_kind="timeline_artifact",
    )


def test_classification_recognizes_quoted_frontmatter_report_kind() -> None:
    _assert_classification(
        user_content="输出 artifact",
        final_content='---\nkind: "report"\nowner: nanobot\n---\nSummary: service unhealthy',
        expected_kind="report_artifact",
    )


def test_classification_recognizes_single_quoted_frontmatter_timeline_output_kind() -> None:
    _assert_classification(
        user_content="输出 artifact",
        final_content="---\noutput_kind: 'timeline'\nscope: readonly\n---\nEvent: timeout spike",
        expected_kind="timeline_artifact",
    )


def test_classification_returns_root_cause_candidate_for_candidate_like_content() -> None:
    _assert_classification(
        user_content="给我一个 root cause candidate",
        final_content="# Root Cause Candidate\nCandidate: 数据库连接池耗尽\nConfidence: medium",
        expected_kind="root_cause_candidate",
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
            "# Timeline\n- 10:00 服务启动\n- 10:05 开始报错\n- 10:08 恢复"
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
