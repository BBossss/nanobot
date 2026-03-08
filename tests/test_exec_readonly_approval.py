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


def test_exec_readonly_allows_ssh_bridge_for_allowlisted_remote_command(tmp_path: Path) -> None:
    tool = ExecTool(
        readonly_mode=True,
        allowed_commands=["cat", "tail", "grep", "systemctl"],
        approval_file=str(tmp_path / "approvals.json"),
        allow_ssh_bridge=True,
        allowed_ssh_hosts=["10.10.10.8"],
    )
    err = tool._guard_command("ssh root@10.10.10.8 systemctl status upgrade-worker", str(tmp_path))
    assert err is None


def test_exec_readonly_blocks_ssh_bridge_for_non_allowlisted_host(tmp_path: Path) -> None:
    tool = ExecTool(
        readonly_mode=True,
        allowed_commands=["cat", "tail", "grep", "systemctl"],
        approval_file=str(tmp_path / "approvals.json"),
        allow_ssh_bridge=True,
        allowed_ssh_hosts=["10.10.10.8"],
    )
    err = tool._guard_command("ssh root@10.10.10.9 systemctl status upgrade-worker", str(tmp_path))
    assert err is not None
    assert "approved host list" in err


def test_exec_readonly_blocks_ssh_bridge_for_disallowed_remote_command(tmp_path: Path) -> None:
    tool = ExecTool(
        readonly_mode=True,
        allowed_commands=["cat", "tail", "grep"],
        approval_file=str(tmp_path / "approvals.json"),
        allow_ssh_bridge=True,
        allowed_ssh_hosts=["10.10.10.8"],
    )
    err = tool._guard_command("ssh root@10.10.10.8 systemctl restart kubelet", str(tmp_path))
    assert err is not None
    assert "manual approval" in err


async def _run_exec(tool: ExecTool, command: str, cwd: Path) -> str:
    return await tool.execute(command=command, working_dir=str(cwd))


def test_exec_writes_audit_record_for_blocked_command(tmp_path: Path) -> None:
    tool = ExecTool(
        readonly_mode=True,
        allowed_commands=["ls"],
        approval_file=str(tmp_path / "approvals.json"),
        working_dir=str(tmp_path),
    )

    import asyncio

    result = asyncio.run(_run_exec(tool, "systemctl restart kubelet", tmp_path))
    assert "manual approval" in result

    audit_file = tmp_path / "audit" / "commands.jsonl"
    assert audit_file.exists()
    payload = json.loads(audit_file.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["source"] == "exec"
    assert payload["status"] == "blocked"
    assert payload["command"] == "systemctl restart kubelet"


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
