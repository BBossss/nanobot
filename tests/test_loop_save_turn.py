import json

from nanobot.agent.context import ContextBuilder
from nanobot.agent.loop import AgentLoop
from nanobot.session.manager import Session
from nanobot.session.manager import SessionManager


def _mk_loop() -> AgentLoop:
    loop = AgentLoop.__new__(AgentLoop)
    loop._TOOL_RESULT_MAX_CHARS = 500
    return loop


def test_save_turn_skips_multimodal_user_when_only_runtime_context() -> None:
    loop = _mk_loop()
    session = Session(key="test:runtime-only")
    runtime = ContextBuilder._RUNTIME_CONTEXT_TAG + "\nCurrent Time: now (UTC)"

    loop._save_turn(
        session,
        [{"role": "user", "content": [{"type": "text", "text": runtime}]}],
        skip=0,
    )
    assert session.messages == []


def test_save_turn_keeps_image_placeholder_after_runtime_strip() -> None:
    loop = _mk_loop()
    session = Session(key="test:image")
    runtime = ContextBuilder._RUNTIME_CONTEXT_TAG + "\nCurrent Time: now (UTC)"

    loop._save_turn(
        session,
        [{
            "role": "user",
            "content": [
                {"type": "text", "text": runtime},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
            ],
        }],
        skip=0,
    )
    assert session.messages[0]["content"] == [{"type": "text", "text": "[image]"}]


def test_save_turn_redacts_ssh_password_from_tool_calls_before_persisting(tmp_path) -> None:
    loop = _mk_loop()
    session = Session(key="test:ssh-password")

    loop._save_turn(
        session,
        [{
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_exec_1",
                    "type": "function",
                    "function": {
                        "name": "exec",
                        "arguments": json.dumps(
                            {
                                "command": "uptime",
                                "target": "root@example-host",
                                "ssh_password": "secret-123",
                            },
                            ensure_ascii=False,
                        ),
                    },
                }
            ],
        }],
        skip=0,
    )

    manager = SessionManager(tmp_path)
    manager.save(session)
    saved_text = manager._get_session_path(session.key).read_text(encoding="utf-8")

    assert "secret-123" not in saved_text
