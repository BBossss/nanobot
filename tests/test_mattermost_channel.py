import json
from unittest.mock import AsyncMock

import pytest

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.mattermost import MattermostChannel
from nanobot.config.schema import MattermostConfig


def _channel() -> MattermostChannel:
    cfg = MattermostConfig(
        enabled=True,
        base_url="https://mm.example.com",
        token="x-token",
        allow_from=["*"],
    )
    return MattermostChannel(cfg, MessageBus())


def test_mattermost_to_ws_url() -> None:
    assert MattermostChannel._to_ws_url("https://mm.example.com") == "wss://mm.example.com/api/v4/websocket"
    assert MattermostChannel._to_ws_url("http://mm.example.com") == "ws://mm.example.com/api/v4/websocket"


def test_mattermost_extract_posted_message() -> None:
    post = {
        "id": "p1",
        "channel_id": "c1",
        "user_id": "u1",
        "message": "check logs",
        "root_id": "r1",
    }
    event = {"event": "posted", "data": {"post": json.dumps(post)}}
    parsed = MattermostChannel._extract_posted_message(json.dumps(event))
    assert parsed is not None
    assert parsed["sender_id"] == "u1"
    assert parsed["thread_id"] == "r1"
    assert parsed["content"] == "check logs"


@pytest.mark.asyncio
async def test_mattermost_send_uses_thread_id_from_metadata() -> None:
    channel = _channel()
    channel._api_post = AsyncMock(return_value={"id": "new-post"})  # type: ignore[method-assign]

    msg = OutboundMessage(
        channel="mattermost",
        chat_id="c1",
        content="result",
        metadata={"thread_id": "r1"},
    )
    await channel.send(msg)
    channel._api_post.assert_awaited_once()
    args = channel._api_post.await_args.args
    assert args[0] == "/api/v4/posts"
    assert args[1]["root_id"] == "r1"


@pytest.mark.asyncio
async def test_mattermost_send_uses_reply_to_over_metadata() -> None:
    channel = _channel()
    channel._api_post = AsyncMock(return_value={"id": "new-post"})  # type: ignore[method-assign]

    msg = OutboundMessage(
        channel="mattermost",
        chat_id="c1",
        content="result",
        reply_to="reply-root",
        metadata={"thread_id": "r1"},
    )
    await channel.send(msg)
    args = channel._api_post.await_args.args
    assert args[1]["root_id"] == "reply-root"
