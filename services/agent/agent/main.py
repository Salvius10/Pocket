"""agent: live voice mascot, UI composer, Pulse, guardrail. Never touches the database."""

from __future__ import annotations

import hmac
import json
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from agent.composer import service as composer
from agent.config import get_settings
from agent.core_client import CoreError, core
from agent.live.fake_bridge import FakeBridge
from agent.live.session import Bridge, LiveSession
from agent.pulse import service as pulse

log = logging.getLogger("agent")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, Any] = {"severity": record.levelname, "logger": record.name, "message": record.getMessage()}
        if record.exc_info:
            out["exception"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.getLogger().handlers[:] = [handler]
    logging.getLogger().setLevel(logging.INFO)
    s = get_settings()  # raises if GEMINI_MODE=live without a key
    log.info("agent starting mode=%s live_model=%s flash_model=%s", s.gemini_mode, s.model_live, s.model_flash)
    yield
    await core().close()


app = FastAPI(title="Pocket agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
                   allow_methods=["*"], allow_headers=["*"])


def require_internal(x_internal_token: Annotated[str | None, Header()] = None) -> None:
    if not x_internal_token or not hmac.compare_digest(x_internal_token, get_settings().internal_token):
        raise HTTPException(403, "internal endpoint")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "agent", "mode": get_settings().gemini_mode}


@app.get("/v1/config")
async def config() -> dict[str, Any]:
    """What the phone needs to know: whether voice is live. Never any key."""
    s = get_settings()
    return {"mode": s.gemini_mode, "voice": s.is_live, "audio_in": {"encoding": "pcm16", "rate": 16000}, "audio_out": {"encoding": "pcm16", "rate": 24000}}


@app.post("/v1/compose", dependencies=[Depends(require_internal)])
async def compose(body: dict[str, Any]) -> dict[str, Any]:
    if "default" not in body:
        raise HTTPException(422, "default layout is required")
    return await composer.compose(body)


@app.post("/internal/jobs/pulse", dependencies=[Depends(require_internal)])
async def job_pulse() -> dict[str, Any]:
    try:
        return await pulse.build_pulse()
    except CoreError as exc:
        raise HTTPException(502, str(exc)) from exc


def _bridge_for(session: LiveSession) -> Bridge:
    if get_settings().is_live:
        from agent.live.adk_bridge import AdkBridge

        return AdkBridge(session)
    return FakeBridge(session)


@app.websocket("/v1/live")
async def live(ws: WebSocket) -> None:
    await ws.accept()
    bridge: Bridge | None = None
    try:
        hello = json.loads(await ws.receive_text())
        if hello.get("type") != "hello":
            await ws.send_text(json.dumps({"type": "error", "message": "first message must be hello"}))
            await ws.close(code=4400)
            return
        mode = "onboarding" if hello.get("mode") == "onboarding" else "chat"
        try:
            who = await core().resolve(hello.get("token"), hello.get("dev_user"), mode)
        except CoreError:
            await ws.send_text(json.dumps({"type": "error", "message": "sign-in failed"}))
            await ws.close(code=4401)
            return
        me = who["me"]
        lang = hello.get("lang") if hello.get("lang") in ("en", "hi", "ta") else me["language"]
        session = LiveSession(ws, user_id=who["user_id"], session_id=who["session_id"], lang=lang, voice=str(hello.get("voice") or me["mascot_voice"]),
                              mode=mode, first_name=me.get("first_name") or "", linked=bool(who.get("linked")), names=who.get("names") or {},
                              debug=bool(hello.get("debug")))
        bridge = _bridge_for(session)
        session.bridge = bridge
        await session.send("ready", session_id=session.session_id, mode=get_settings().gemini_mode, voice=get_settings().is_live, lang=lang)
        await bridge.start()
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                await bridge.on_audio(msg["bytes"])
                continue
            try:
                data = json.loads(msg.get("text") or "{}")
            except json.JSONDecodeError:
                continue
            kind = data.get("type")
            if kind == "text" and str(data.get("text") or "").strip():
                await bridge.on_text(str(data["text"]).strip()[:1000])
            elif kind == "audio_end":
                await bridge.on_audio_end()
            elif kind == "bye":
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("live socket error")
    finally:
        if bridge is not None:
            await bridge.close()
