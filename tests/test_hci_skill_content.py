from pathlib import Path


def test_hci_troubleshooting_skill_mentions_remote_readonly_rules() -> None:
    path = Path("nanobot/skills/hci-troubleshooting/SKILL.md")
    text = path.read_text(encoding="utf-8")

    assert "远程只读排查规则" in text
    assert "`exec`" in text
    assert "`target`" in text
    assert "不要直接拼写 `ssh ...`" in text
    assert "CLI" in text
    assert "目标主机" in text
    assert "明文密码" in text
    assert "信息收集规则" in text
    assert "建议动作分级" in text
    assert "历史案例引用规则" in text
    assert "多主机证据组织规则" in text
    assert "服务日志映射表使用规则" in text
    assert "references/service-log-map.md" in text
    assert "`find_logs`" in text
    assert "`read_log_tail`" in text
    assert "`search_log`" in text
    assert "`service_status`" in text
    assert "`process_snapshot`" in text
    assert "`journal_tail`" in text
    assert "`disk_snapshot`" in text
    assert "`network_snapshot`" in text
    assert "`find_recent_files`" in text


def test_hci_storage_network_sop_mentions_remote_checks() -> None:
    path = Path("nanobot/skills/hci-storage-network-sop/SKILL.md")
    text = path.read_text(encoding="utf-8")

    assert "远程专项检查规则" in text
    assert "`exec`" in text
    assert "`target`" in text
    assert "不要直接拼写 `ssh ...`" in text
    assert "目标主机" in text
    assert "与其他节点" in text


def test_hci_service_log_map_contains_known_upgrade_logs() -> None:
    path = Path("nanobot/skills/hci-troubleshooting/references/service-log-map.md")
    text = path.read_text(encoding="utf-8")

    assert "/sf/log/today/upgrade-server.log" in text
    assert "/sf/log/today/upgrade-worker.log" in text
    assert "/sf/log/today/update.log" in text
    assert "/sf/log/blackbox/" in text
    assert "/sf/log/vn-blackbox/" in text
