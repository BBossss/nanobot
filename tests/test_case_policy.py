from nanobot.policies.cases import CaseRecordPolicy


def test_case_policy_should_record_every_turn() -> None:
    assert CaseRecordPolicy.should_record("任意消息", "every_turn") is True


def test_case_policy_should_record_manual() -> None:
    assert CaseRecordPolicy.should_record("生成案例摘要", "manual") is False


def test_case_policy_should_record_end_only_with_end_markers() -> None:
    assert CaseRecordPolicy.should_record("查完了，结束吧", "end_only") is True
    assert CaseRecordPolicy.should_record("请生成案例摘要", "end_only") is True


def test_case_policy_should_record_end_only_ignores_question() -> None:
    assert CaseRecordPolicy.should_record("这个摘要保存了吗", "end_only") is False
    assert CaseRecordPolicy.should_record("要不要保存案例？", "end_only") is False


def test_case_policy_build_generated_case() -> None:
    draft = CaseRecordPolicy.build_generated_case(
        channel="telegram",
        content="节点 CPU 异常",
        final_content="建议先采样再确认根因",
    )
    assert draft.title == "节点 CPU 异常"
    assert draft.trigger == "telegram"
    assert draft.source == "generated"
    assert draft.tags == ["telegram"]
    assert "Collected from request/response flow" == draft.evidence
