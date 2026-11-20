"""The agent's only door to money: core-api internal endpoints. No database access from here."""

from __future__ import annotations

from typing import Any

import httpx

from agent.config import get_settings


class CoreError(RuntimeError):
    pass


class CoreClient:
    def __init__(self) -> None:
        s = get_settings()
        self._client = httpx.AsyncClient(base_url=s.core_api_url, timeout=30, headers={"X-Internal-Token": s.internal_token})

    async def close(self) -> None:
        await self._client.aclose()

    async def _post(self, path: str, body: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
        headers = {"X-Pocket-User-Id": user_id} if user_id else {}
        try:
            r = await self._client.post(path, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise CoreError(f"core-api unreachable: {type(exc).__name__}") from exc
        if r.status_code >= 400:
            detail = r.json().get("detail") if r.headers.get("content-type", "").startswith("application/json") else r.text[:200]
            raise CoreError(str(detail))
        return r.json()  # type: ignore[no-any-return]

    async def resolve(self, token: str | None, dev_user: str | None, mode: str) -> dict[str, Any]:
        return await self._post("/internal/auth/resolve", {"token": token, "dev_user": dev_user, "mode": mode})

    async def tool(self, user_id: str, name: str, args: dict[str, Any], session_id: str | None = None) -> dict[str, Any]:
        return await self._post(f"/internal/tools/{name}", {"args": args, "session_id": session_id}, user_id)

    async def turn(self, user_id: str, session_id: str, role: str, text: str) -> None:
        if text.strip():
            try:
                await self._post("/internal/chat/turn", {"session_id": session_id, "role": role, "text": text[:4000]}, user_id)
            except CoreError:
                pass  # a lost transcript row must not break the conversation

    async def guard_event(self, user_id: str, session_id: str | None, kind: str, detail: dict[str, Any]) -> None:
        try:
            await self._post("/internal/guard/event", {"session_id": session_id, "kind": kind, "detail": detail}, user_id)
        except CoreError:
            pass

    async def put_pulse(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        return await self._post("/internal/pulse/items", {"items": items})


_client: CoreClient | None = None


def core() -> CoreClient:
    global _client
    if _client is None:
        _client = CoreClient()
    return _client
