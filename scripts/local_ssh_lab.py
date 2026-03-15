#!/usr/bin/env python3
"""Manage local SSH loopback services for ExecTool validation."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


LAB_DIR = Path(tempfile.gettempdir()) / "nanobot-ssh-lab"
PUBKEY_PORT = 2322
PASSWORD_PORT = 2323
PASSWORD_USERNAME = "nanobot"
PASSWORD_VALUE = "secret-123"


def build_sshd_config(authorized_keys: Path, host_key: Path, pid_file: Path, port: int) -> str:
    """Render sshd config for the local pubkey loopback server."""
    return "\n".join(
        [
            f"Port {port}",
            "ListenAddress 127.0.0.1",
            f"HostKey {host_key}",
            f"PidFile {pid_file}",
            f"AuthorizedKeysFile {authorized_keys}",
            "PasswordAuthentication no",
            "KbdInteractiveAuthentication no",
            "ChallengeResponseAuthentication no",
            "PubkeyAuthentication yes",
            "UsePAM no",
            "PermitRootLogin no",
            "StrictModes no",
            "LogLevel ERROR",
        ]
    ) + "\n"


def build_password_server_script(host_key: Path, port: int, username: str, password: str) -> str:
    """Render a minimal password-only SSH server backed by Paramiko."""
    payload = {
        "host_key": str(host_key),
        "port": port,
        "username": username,
        "password": password,
    }
    return f"""#!/usr/bin/env python3
from __future__ import annotations

import json
import socket
import subprocess
import threading

import paramiko

CFG = json.loads({json.dumps(json.dumps(payload), ensure_ascii=False)})
HOST = "127.0.0.1"
PORT = CFG["port"]
USERNAME = CFG["username"]
PASSWORD = CFG["password"]
HOST_KEY = paramiko.Ed25519Key(filename=CFG["host_key"])


class DemoServer(paramiko.ServerInterface):
    def __init__(self) -> None:
        self.command = ""
        self.event = threading.Event()

    def check_auth_password(self, username: str, password: str) -> int:
        if username == USERNAME and password == PASSWORD:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username: str) -> str:
        return "password"

    def check_channel_request(self, kind: str, chanid: int) -> int:
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_exec_request(self, channel, command: bytes) -> bool:
        self.command = command.decode("utf-8", errors="replace")
        self.event.set()
        return True


def handle_client(client: socket.socket) -> None:
    transport = paramiko.Transport(client)
    transport.add_server_key(HOST_KEY)
    server = DemoServer()
    channel = None
    try:
        transport.start_server(server=server)
        channel = transport.accept(10)
        if channel is None:
            return
        if not server.event.wait(10):
            channel.send_stderr(b"timed out waiting for exec request\\n")
            channel.send_exit_status(124)
            return
        completed = subprocess.run(
            server.command,
            shell=True,
            capture_output=True,
            text=False,
        )
        if completed.stdout:
            channel.sendall(completed.stdout)
        if completed.stderr:
            channel.send_stderr(completed.stderr)
        channel.send_exit_status(completed.returncode)
    finally:
        if channel is not None:
            try:
                channel.close()
            except Exception:
                pass
        transport.close()
        client.close()


def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen(100)
    print(f"password ssh server listening on {{HOST}}:{{PORT}}", flush=True)
    while True:
        client, _addr = sock.accept()
        thread = threading.Thread(target=handle_client, args=(client,), daemon=True)
        thread.start()


if __name__ == "__main__":
    main()
"""


def _paths() -> dict[str, Path]:
    """Return runtime paths for the local SSH lab."""
    return {
        "lab_dir": LAB_DIR,
        "authorized_keys": LAB_DIR / "authorized_keys",
        "host_key": LAB_DIR / "ssh_host_ed25519_key",
        "host_key_pub": LAB_DIR / "ssh_host_ed25519_key.pub",
        "sshd_config": LAB_DIR / "sshd_config",
        "sshd_pid": LAB_DIR / "sshd.pid",
        "sshd_out": LAB_DIR / "sshd.out",
        "password_server": LAB_DIR / "password_ssh_server.py",
        "password_pid": LAB_DIR / "password_ssh_server.pid",
        "password_out": LAB_DIR / "password_ssh_server.out",
    }


def _ensure_lab_files() -> dict[str, Path]:
    paths = _paths()
    paths["lab_dir"].mkdir(parents=True, exist_ok=True)

    pubkey = Path.home() / ".ssh" / "id_rsa.pub"
    if not pubkey.exists():
        raise SystemExit(f"Missing public key: {pubkey}")
    paths["authorized_keys"].write_text(pubkey.read_text(encoding="utf-8"), encoding="utf-8")

    if not paths["host_key"].exists():
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(paths["host_key"])],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    paths["sshd_config"].write_text(
        build_sshd_config(
            authorized_keys=paths["authorized_keys"],
            host_key=paths["host_key"],
            pid_file=paths["sshd_pid"],
            port=PUBKEY_PORT,
        ),
        encoding="utf-8",
    )
    paths["password_server"].write_text(
        build_password_server_script(
            host_key=paths["host_key"],
            port=PASSWORD_PORT,
            username=PASSWORD_USERNAME,
            password=PASSWORD_VALUE,
        ),
        encoding="utf-8",
    )
    os.chmod(paths["password_server"], 0o755)
    return paths


def _pid_is_running(pid_file: Path) -> bool:
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except Exception:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _wait_for_port(port: int, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _wait_for_pid_file(pid_file: Path, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _pid_is_running(pid_file):
            return True
        time.sleep(0.1)
    return False


def _start_pubkey_sshd(paths: dict[str, Path]) -> None:
    if _pid_is_running(paths["sshd_pid"]):
        return
    with paths["sshd_out"].open("ab") as out:
        subprocess.Popen(
            ["/usr/sbin/sshd", "-e", "-f", str(paths["sshd_config"])],
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    if not _wait_for_pid_file(paths["sshd_pid"]) or not _wait_for_port(PUBKEY_PORT):
        raise SystemExit(f"Failed to start local pubkey sshd on 127.0.0.1:{PUBKEY_PORT}")


def _start_password_server(paths: dict[str, Path]) -> None:
    if _pid_is_running(paths["password_pid"]):
        return
    with paths["password_out"].open("ab") as out:
        proc = subprocess.Popen(
            [sys.executable, str(paths["password_server"])],
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    paths["password_pid"].write_text(f"{proc.pid}\n", encoding="utf-8")
    if not _wait_for_port(PASSWORD_PORT):
        raise SystemExit(f"Failed to start local password SSH server on 127.0.0.1:{PASSWORD_PORT}")


def _update_known_hosts() -> None:
    known_hosts = Path.home() / ".ssh" / "known_hosts"
    known_hosts.parent.mkdir(parents=True, exist_ok=True)
    for port in (PUBKEY_PORT, PASSWORD_PORT):
        subprocess.run(
            ["ssh-keygen", "-R", f"[127.0.0.1]:{port}", "-f", str(known_hosts)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        scan = subprocess.run(
            ["ssh-keyscan", "-p", str(port), "127.0.0.1"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        with known_hosts.open("a", encoding="utf-8") as f:
            if scan.stdout:
                f.write(scan.stdout)


def _stop_pid(pid_file: Path) -> None:
    if not pid_file.exists():
        return
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except Exception:
        pid_file.unlink(missing_ok=True)
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    pid_file.unlink(missing_ok=True)


def _status_payload(paths: dict[str, Path]) -> dict[str, object]:
    user = getpass.getuser()
    return {
        "lab_dir": str(paths["lab_dir"]),
        "pubkey": {
            "port": PUBKEY_PORT,
            "running": _pid_is_running(paths["sshd_pid"]),
            "target": f"{user}@127.0.0.1:{PUBKEY_PORT}",
        },
        "password": {
            "port": PASSWORD_PORT,
            "running": _pid_is_running(paths["password_pid"]),
            "target": f"{PASSWORD_USERNAME}@127.0.0.1:{PASSWORD_PORT}",
            "username": PASSWORD_USERNAME,
            "password": PASSWORD_VALUE,
        },
    }


def cmd_start() -> int:
    paths = _ensure_lab_files()
    _start_pubkey_sshd(paths)
    _start_password_server(paths)
    _update_known_hosts()
    payload = _status_payload(paths)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_status() -> int:
    paths = _paths()
    print(json.dumps(_status_payload(paths), ensure_ascii=False, indent=2))
    return 0


def cmd_stop() -> int:
    paths = _paths()
    _stop_pid(paths["password_pid"])
    _stop_pid(paths["sshd_pid"])
    print(json.dumps(_status_payload(paths), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local SSH loopback lab services")
    parser.add_argument("action", choices=["start", "status", "stop"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.action == "start":
        return cmd_start()
    if args.action == "status":
        return cmd_status()
    return cmd_stop()


if __name__ == "__main__":
    raise SystemExit(main())
