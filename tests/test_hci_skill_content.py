from pathlib import Path


def test_hci_troubleshooting_skill_mentions_remote_readonly_rules() -> None:
    path = Path("nanobot/skills/hci-troubleshooting/SKILL.md")
    text = path.read_text(encoding="utf-8")

    assert "远程只读排查规则" in text
    assert "目标主机" in text
    assert "明文密码" in text
    assert "信息收集规则" in text
    assert "建议动作分级" in text
    assert "历史案例引用规则" in text
    assert "多主机证据组织规则" in text


def test_hci_storage_network_sop_mentions_remote_checks() -> None:
    path = Path("nanobot/skills/hci-storage-network-sop/SKILL.md")
    text = path.read_text(encoding="utf-8")

    assert "远程专项检查规则" in text
    assert "目标主机" in text
    assert "与其他节点" in text
