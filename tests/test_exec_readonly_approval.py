import json
from pathlib import Path

from typer.testing import CliRunner

from nanobot.agent.tools.shell import ExecTool
from nanobot.cli.commands import app
from nanobot.config.schema import Config


runner = CliRunner()


def test_exec_readonly_blocks_non_allowlisted_command(tmp_path: Path) -> None:
    tool = ExecTool(
        readonly_mode=True,
        allowed_commands=["ls", "cat"],
        approval_file=str(tmp_path / "approvals.json"),
    )
    err = tool._guard_command("systemctl restart kubelet", str(tmp_path))
    assert err is not None
    assert "manual approval" in err


def test_exec_readonly_allows_allowlisted_base_command(tmp_path: Path) -> None:
    tool = ExecTool(
        readonly_mode=True,
        allowed_commands=["systemctl"],
        approval_file=str(tmp_path / "approvals.json"),
    )
    err = tool._guard_command("systemctl status kubelet", str(tmp_path))
    assert err is None


def test_exec_readonly_allows_manually_approved_exact_command(tmp_path: Path) -> None:
    approval_file = tmp_path / "approvals.json"
    approval_file.write_text(json.dumps({"commands": ["systemctl restart kubelet"]}), encoding="utf-8")

    tool = ExecTool(
        readonly_mode=True,
        allowed_commands=["ls"],
        approval_file=str(approval_file),
    )
    err = tool._guard_command("systemctl restart kubelet", str(tmp_path))
    assert err is None


def test_approvals_cli_grant_list_revoke(tmp_path: Path, monkeypatch) -> None:
    cfg = Config()
    cfg.tools.exec.approval_file = str(tmp_path / "approvals" / "exec_allow.json")
    monkeypatch.setattr("nanobot.config.loader.load_config", lambda: cfg)

    grant = runner.invoke(app, ["approvals", "grant", "--command", "systemctl restart kubelet"])
    assert grant.exit_code == 0
    assert "Approved" in grant.stdout

    listed = runner.invoke(app, ["approvals", "list"])
    assert listed.exit_code == 0
    assert "systemctl restart kubelet" in listed.stdout

    revoke = runner.invoke(app, ["approvals", "revoke", "--command", "systemctl restart kubelet"])
    assert revoke.exit_code == 0
    assert "Revoked" in revoke.stdout
