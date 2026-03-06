"""Mattermost channel integration."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import websockets
from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import MattermostConfig


class MattermostChannel(BaseChannel):
    """Mattermost channel via websocket events and REST replies."""

    name = "mattermost"

    def __init__(self, config: MattermostConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: MattermostConfig = config
        self._client = httpx.AsyncClient(timeout=30.0)
        self._bot_user_id: str = ""
        self._ws: websockets.ClientConnection | None = None

    async def start(self) -> None:
        if not self.config.base_url or not self.config.token:
            raise RuntimeError("Mattermost base_url/token not configured")
        self._running = True
        await self._load_bot_user()
        while self._running:
            try:
                ws_url = self._to_ws_url(self.config.base_url)
                headers = {"Authorization": f"Bearer {self.config.token}"}
                async with websockets.connect(ws_url, additional_headers=headers) as ws:
                    self._ws = ws
                    logger.info("Mattermost websocket connected")
                    while self._running:
                        raw = await ws.recv()
                        if not isinstance(raw, str):
                            continue
                        event = self._extract_posted_message(raw)
                        if not event:
                            continue
                        if event["sender_id"] == self._bot_user_id:
                            continue
                        await self._handle_message(
                            sender_id=event["sender_id"],
                            chat_id=event["channel_id"],
                            content=event["content"],
                            metadata={"post_id": event["post_id"], "thread_id": event["thread_id"]},
                            session_key=f"{self.name}:{event['channel_id']}:{event['thread_id']}",
                        )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("Mattermost websocket loop error: {}", e)
                await asyncio.sleep(2)

    async def stop(self) -> None:
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        await self._client.aclose()

    async def send(self, msg: OutboundMessage) -> None:
        payload: dict[str, Any] = {
            "channel_id": msg.chat_id,
            "message": msg.content,
        }
        thread_id = msg.reply_to or (msg.metadata or {}).get("thread_id")
        if thread_id:
            payload["root_id"] = thread_id
        await self._api_post("/api/v4/posts", payload)

    async def _load_bot_user(self) -> None:
        me = await self._api_get("/api/v4/users/me")
        self._bot_user_id = str(me.get("id", ""))
        if not self._bot_user_id:
            raise RuntimeError("Unable to resolve Mattermost bot user id")

    async def _api_get(self, path: str) -> dict[str, Any]:
        r = await self._client.get(
            f"{self.config.base_url.rstrip('/')}{path}",
            headers={"Authorization": f"Bearer {self.config.token}"},
        )
        r.raise_for_status()
        return r.json()

    async def _api_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        r = await self._client.post(
            f"{self.config.base_url.rstrip('/')}{path}",
            json=payload,
            headers={"Authorization": f"Bearer {self.config.token}"},
        )
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _to_ws_url(base_url: str) -> str:
        base = base_url.rstrip("/")
        if base.startswith("https://"):
            return "wss://" + base[len("https://") :] + "/api/v4/websocket"
        if base.startswith("http://"):
            return "ws://" + base[len("http://") :] + "/api/v4/websocket"
        raise ValueError("Mattermost base_url must start with http:// or https://")

    @staticmethod
    def _extract_posted_message(raw_event: str) -> dict[str, str] | None:
        try:
            event = json.loads(raw_event)
            if event.get("event") != "posted":
                return None
            data = event.get("data") or {}
            post_raw = data.get("post")
            if not isinstance(post_raw, str):
                return None
            post = json.loads(post_raw)
            sender_id = str(post.get("user_id", ""))
            channel_id = str(post.get("channel_id", ""))
            post_id = str(post.get("id", ""))
            content = str(post.get("message", "")).strip()
            if not sender_id or not channel_id or not post_id or not content:
                return None
            thread_id = str(post.get("root_id") or post_id)
            return {
                "sender_id": sender_id,
                "channel_id": channel_id,
                "post_id": post_id,
                "thread_id": thread_id,
                "content": content,
            }
        except Exception:
            return None
