from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_exec_ssh_loopback_acceptance.py"
SPEC = spec_from_file_location("run_exec_ssh_loopback_acceptance", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
acceptance = module_from_spec(SPEC)
SPEC.loader.exec_module(acceptance)


def test_validate_lab_status_requires_both_targets_running() -> None:
    errors = acceptance.validate_lab_status(
        {
            "pubkey": {"running": True, "target": "me@127.0.0.1:2322"},
            "password": {"running": False, "target": "nanobot@127.0.0.1:2323"},
        }
    )

    assert errors == ["password target is not running"]


def test_build_targets_uses_expected_loopback_ports() -> None:
    targets = acceptance.build_targets("alice")

    assert targets["pubkey"] == "alice@127.0.0.1:2322"
    assert targets["password"] == "nanobot@127.0.0.1:2323"
