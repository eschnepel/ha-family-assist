from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Protocol

import aiohttp

SUPERVISOR_WS = "ws://supervisor/core/websocket"


class UserDirectoryError(Exception):
    pass


@dataclass(frozen=True)
class HAUser:
    id: str
    name: str
    is_admin: bool


class UserDirectory(Protocol):
    async def users(self) -> list[HAUser]: ...


class SupervisorUsers:
    """Home Assistant users, fetched through the Supervisor's core websocket proxy."""

    def __init__(self, token: str, *, ttl: float = 60.0):
        self._token = token
        self._ttl = ttl
        self._cache: list[HAUser] = []
        self._fetched = 0.0
        self._lock = asyncio.Lock()

    async def users(self) -> list[HAUser]:
        async with self._lock:
            if self._cache and time.monotonic() - self._fetched < self._ttl:
                return self._cache
            self._cache = await self._fetch()
            self._fetched = time.monotonic()
            return self._cache

    async def _fetch(self) -> list[HAUser]:
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.ws_connect(
                    SUPERVISOR_WS,
                    timeout=10,  # type: ignore[call-overload]  # int accepted at runtime
                ) as ws,
            ):
                await ws.receive_json(timeout=10)
                await ws.send_json({"type": "auth", "access_token": self._token})
                if (await ws.receive_json(timeout=10)).get("type") != "auth_ok":
                    raise UserDirectoryError("Home Assistant rejected the add-on token")
                await ws.send_json({"id": 1, "type": "config/auth/list"})
                while True:
                    message = await ws.receive_json(timeout=10)
                    if message.get("id") == 1:
                        break
        except (TimeoutError, aiohttp.ClientError, ValueError) as exc:
            raise UserDirectoryError(
                f"Cannot read Home Assistant users ({type(exc).__name__})"
            ) from None
        if not message.get("success"):
            raise UserDirectoryError("Home Assistant refused to list users")
        users = []
        for raw in message.get("result", []):
            if raw.get("system_generated") or not raw.get("is_active", True):
                continue
            is_admin = bool(raw.get("is_owner")) or "system-admin" in raw.get("group_ids", [])
            users.append(
                HAUser(
                    str(raw["id"]),
                    str(raw.get("name") or raw.get("username") or raw["id"]),
                    is_admin,
                )
            )
        return users


class StaticUsers:
    """Fixed users for development and tests."""

    def __init__(self, users: list[HAUser]):
        self._users = users

    async def users(self) -> list[HAUser]:
        return self._users
