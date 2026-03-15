from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "local_ssh_lab.py"
SPEC = spec_from_file_location("local_ssh_lab", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
local_ssh_lab = module_from_spec(SPEC)
SPEC.loader.exec_module(local_ssh_lab)


def test_build_sshd_config_contains_expected_paths_and_port(tmp_path) -> None:
    config = local_ssh_lab.build_sshd_config(
        authorized_keys=tmp_path / "authorized_keys",
        host_key=tmp_path / "ssh_host_ed25519_key",
        pid_file=tmp_path / "sshd.pid",
        port=2322,
    )

    assert "Port 2322" in config
    assert f"AuthorizedKeysFile {tmp_path / 'authorized_keys'}" in config
    assert f"HostKey {tmp_path / 'ssh_host_ed25519_key'}" in config
    assert f"PidFile {tmp_path / 'sshd.pid'}" in config


def test_build_password_server_script_contains_expected_runtime_values(tmp_path) -> None:
    script = local_ssh_lab.build_password_server_script(
        host_key=tmp_path / "ssh_host_ed25519_key",
        port=2323,
        username="nanobot",
        password="secret-123",
    )

    assert str(tmp_path / "ssh_host_ed25519_key") in script
    assert '\\"port\\": 2323' in script
    assert '\\"username\\": \\"nanobot\\"' in script
    assert '\\"password\\": \\"secret-123\\"' in script


def test_main_dispatches_to_status(monkeypatch) -> None:
    calls = []

    def fake_status() -> int:
        calls.append("status")
        return 7

    monkeypatch.setattr(local_ssh_lab, "cmd_status", fake_status)

    exit_code = local_ssh_lab.main(["status"])

    assert exit_code == 7
    assert calls == ["status"]
