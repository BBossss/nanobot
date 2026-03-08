from pathlib import Path

from nanobot.agent.skills import SkillsLoader


def test_hci_skills_are_discoverable(tmp_path: Path) -> None:
    loader = SkillsLoader(workspace=tmp_path)
    names = {skill["name"] for skill in loader.list_skills(filter_unavailable=False)}

    assert "hci-troubleshooting" in names
    assert "hci-inspection-analysis" in names
    assert "hci-case-summary" in names
    assert "hci-storage-network-sop" in names


def test_hci_troubleshooting_is_loaded_as_always_skill(tmp_path: Path) -> None:
    loader = SkillsLoader(workspace=tmp_path)
    always_skills = loader.get_always_skills()

    assert "hci-troubleshooting" in always_skills
