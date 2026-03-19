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


def test_classification_returns_root_cause_candidate_for_candidate_like_content() -> None:
    _assert_classification(
        user_content="给我一个 root cause candidate",
        final_content="# Root Cause Candidate\nCandidate: 数据库连接池耗尽\nConfidence: medium",
        expected_kind="root_cause_candidate",
    )
