from nanobot.agent.loop import AgentLoop


def test_should_record_case_every_turn() -> None:
    assert AgentLoop._should_record_case("任意消息", "every_turn") is True


def test_should_record_case_manual() -> None:
    assert AgentLoop._should_record_case("生成案例摘要", "manual") is False


def test_should_record_case_end_only_with_end_markers() -> None:
    assert AgentLoop._should_record_case("查完了，结束吧", "end_only") is True
    assert AgentLoop._should_record_case("请生成案例摘要", "end_only") is True


def test_should_record_case_end_only_ignores_question() -> None:
    assert AgentLoop._should_record_case("这个摘要保存了吗", "end_only") is False
    assert AgentLoop._should_record_case("要不要保存案例？", "end_only") is False
