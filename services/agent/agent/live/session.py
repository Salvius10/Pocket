"""One live conversation over the phone's WebSocket (ARCHITECTURE.md §7.1).

Binary frames up: mic PCM16 LE mono 16 kHz. Binary frames down: mascot PCM16 LE mono 24 kHz.
Text frames: JSON control messages. The session owns the guardrail: it tracks the numbers tools
returned, watches every sentence of mascot transcript, and on a violation stops audio for the
rest of the turn and asks the bridge to correct itself.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from fastapi import WebSocket, WebSocketDisconnect
from pocket_common import guard

from agent.core_client import CoreError, core
from agent.mascot.tools import TOOL_NAMES
from agent.prompts.lines import line

log = logging.getLogger("agent.live")

MOODS = ("idle", "listening", "thinking", "talking", "happy", "concerned", "celebrating", "sleepy")
FORWARDED_EVENTS = ("confirm_request", "show_widget", "home_updated", "profile_saved")


class Bridge(Protocol):
    async def start(self) -> None: ...
    async def on_text(self, text: str) -> None: ...
    async def on_audio(self, pcm: bytes) -> None: ...
    async def on_audio_end(self) -> None: ...
    async def correct(self, instruction: str) -> None: ...
    async def close(self) -> None: ...


class LiveSession:
    def __init__(self, ws: WebSocket, *, user_id: str, session_id: str, lang: str, voice: str, mode: str,
                 first_name: str, linked: bool, names: dict[str, list[str]], debug: bool = False) -> None:
        self.ws = ws
        self.user_id, self.session_id = user_id, session_id
        self.lang, self.voice, self.mode = lang, voice, mode
        self.first_name, self.linked, self.names = first_name, linked, names
        self.debug = debug  # evals ask for the allowed-number set so they can check Gate 3
        self.allowed: set[float] = set()
        self.tools_called: list[str] = []
        self.turn_tools: list[str] = []
        self._buffer = ""
        self._turn_text = ""
        self._audio_blocked = False
        self._violations = 0
        self.bridge: Bridge | None = None
        self.closed = False

    # ---- to the phone ----
    async def send(self, type_: str, **payload: Any) -> None:
        if self.closed:
            return
        try:
            await self.ws.send_text(json.dumps({"type": type_, **payload}, ensure_ascii=False))
        except (WebSocketDisconnect, RuntimeError):
            self.closed = True  # the phone went away: stop sending, let the tool or turn finish quietly

    async def mood(self, mood: str) -> None:
        if mood in MOODS:
            await self.send("mood", mood=mood)

    async def send_audio(self, pcm: bytes) -> None:
        if self._audio_blocked or self.closed:
            return
        try:
            await self.ws.send_bytes(pcm)
        except (WebSocketDisconnect, RuntimeError):
            self.closed = True

    # ---- user side ----
    async def user_said(self, text: str, final: bool = True) -> None:
        await self.send("transcript", role="user", text=text, final=final)
        if final:
            self.allowed.update(guard.extract_numbers(text))  # numbers the user said are fair to repeat
            await core().turn(self.user_id, self.session_id, "user", text)

    # ---- tools ----
    async def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Run a tool on core-api. Records its numbers as allowed and forwards phone events."""
        if name not in TOOL_NAMES:
            return {"ok": False, "error": f"unknown tool {name}", "say": ""}
        self.tools_called.append(name)
        self.turn_tools.append(name)
        await self.send("tool", name=name, status="start")
        try:
            out = await core().tool(self.user_id, name, args, self.session_id)
        except CoreError as exc:
            await self.send("tool", name=name, status="error")
            return {"ok": False, "error": str(exc), "say": line(self.lang, "tool_failed")}
        self.allowed.update(guard.numbers_in(out.get("result")))
        self.allowed.update(guard.extract_numbers(out.get("say") or ""))
        client = out.get("client")
        if isinstance(client, dict) and client.get("type") in FORWARDED_EVENTS:
            if client["type"] == "confirm_request" and client.get("proposal"):
                self.allowed.update(guard.numbers_in(client["proposal"]))
            await self.send(client["type"], **{k: v for k, v in client.items() if k != "type"})
        await self.send("tool", name=name, status="done")
        return out

    # ---- mascot side ----
    async def mascot_text(self, chunk: str) -> None:
        """Feed output transcription as it arrives. Guard runs on each completed sentence."""
        if not chunk:
            return
        self._turn_text += chunk
        self._buffer += chunk
        await self.send("transcript", role="mascot", text=self._turn_text, final=False)
        sentences, self._buffer = guard.split_sentences(self._buffer)
        for s in sentences:
            await self._check(s)

    async def _check(self, sentence: str) -> None:
        result = guard.check_sentence(sentence, self.allowed)
        if result.ok or self._audio_blocked:
            return
        self._violations += 1
        self._audio_blocked = True  # stop forwarding audio for the rest of the turn
        await self.send("stop_audio", reason=result.kind)
        await self.mood("concerned")
        await core().guard_event(self.user_id, self.session_id, result.kind or "advice",
                                 {"banned": result.banned, "numbers": result.detail.get("numbers", []), "tools": self.tools_called[-5:]})
        log.warning("guard violation kind=%s banned=%s", result.kind, result.banned)
        if self.bridge is not None:
            if result.kind == "number_mismatch":
                await self.bridge.correct("You said a number that is not in the tool results. Apologise briefly, call the right tool again, "
                                          "and repeat only the numbers it returns.")
            else:
                await self.bridge.correct("You gave investment advice, which you must never do. Take it back briefly, say you cannot tell the "
                                          "user what to buy or sell, and offer facts about their own holdings instead.")

    async def turn_complete(self) -> None:
        if self._buffer.strip():
            await self._check(self._buffer.strip())
        text = self._turn_text.strip()
        if text:
            await self.send("transcript", role="mascot", text=text, final=True)
            await core().turn(self.user_id, self.session_id, "mascot", text)
        self._buffer = self._turn_text = ""
        self._audio_blocked = False
        extra = {"allowed_numbers": sorted(self.allowed)} if self.debug else {}
        await self.send("turn_complete", tools=self.turn_tools, **extra)
        self.turn_tools = []
        await self.mood("idle")

    async def interrupted(self) -> None:
        self.turn_tools = []
        self._buffer = self._turn_text = ""
        self._audio_blocked = False
        await self.send("interrupted")

    async def say(self, text: str, mood: str = "talking") -> None:
        """Speak one complete reply as text (fake mode and fixed lines)."""
        await self.mood(mood)
        await self.mascot_text(text if text.endswith((".", "?", "!", "।")) else text + ".")
        await self.turn_complete()
