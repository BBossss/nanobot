from nanobot.policies.skills import SkillRoutingPolicy


def test_skill_routing_defaults_to_hci_troubleshooting() -> None:
    skills = SkillRoutingPolicy.select_skills(content="介绍一下当前节点状态")

    assert skills == ["hci-troubleshooting"]


def test_skill_routing_adds_case_summary_for_case_wrap_up() -> None:
    skills = SkillRoutingPolicy.select_skills(content="请生成案例摘要并保存")

    assert "hci-troubleshooting" in skills
    assert "hci-case-summary" in skills


def test_skill_routing_adds_inspection_analysis_for_system_event() -> None:
    skills = SkillRoutingPolicy.select_skills(
        content="inspection:run",
        channel="system",
        metadata={"trigger": "inspection"},
    )

    assert "hci-troubleshooting" in skills
    assert "hci-inspection-analysis" in skills


def test_skill_routing_adds_specialty_skill_for_storage_keywords() -> None:
    skills = SkillRoutingPolicy.select_skills(content="存储节点 io latency 升高，帮我排查")

    assert "hci-troubleshooting" in skills
    assert "hci-storage-network-sop" in skills
