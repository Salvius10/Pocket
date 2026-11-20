"""One turn against the live mascot: send a typed line, print what comes back, save the audio.

Cheap check that the Gemini Live path works before spending on the full chat eval.
Run: uv run python evals/smoke_live.py ["your question"] [persona] [lang]     (needs `make dev`)
"""

from __future__ import annotations

import asyncio
import json
import sys
import wave
from pathlib import Path

import httpx
import websockets

CORE, AGENT = "http://127.0.0.1:8080", "ws://127.0.0.1:8081"
OUT = Path(__file__).resolve().parents[1] / ".local" / "smoke_live.wav"


async def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    text = sys.argv[1] if len(sys.argv) > 1 else "How much can I spend today?"
    persona = sys.argv[2] if len(sys.argv) > 2 else "first_job"
    lang = sys.argv[3] if len(sys.argv) > 3 else "en"
    dev_user = f"live-{persona}-{lang}"
    async with httpx.AsyncClient(base_url=CORE, headers={"X-Dev-User": dev_user}, timeout=60) as http:
        await http.patch("/v1/me", json={"language": lang})
        me = (await http.get("/v1/me")).json()
        if me.get("persona_id") != persona:
            (await http.post("/v1/onboarding/link", json={"persona_id": persona})).raise_for_status()

    audio = bytearray()
    ok = False
    async with websockets.connect(f"{AGENT}/v1/live", max_size=None) as ws:
        await ws.send(json.dumps({"type": "hello", "dev_user": dev_user, "lang": lang, "voice": "warm", "mode": "chat", "debug": True}))
        print("<<", await asyncio.wait_for(ws.recv(), timeout=30))
        print(f"YOU: {text}")
        await ws.send(json.dumps({"type": "text", "text": text}))
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=60)
                if isinstance(raw, bytes):
                    audio.extend(raw)
                    continue
                msg = json.loads(raw)
                kind = msg.get("type")
                if kind == "transcript" and msg.get("final"):
                    print(f"{msg['role'].upper()}: {msg['text']}")
                elif kind == "tool":
                    print(f"  tool {msg['name']} {msg['status']}")
                elif kind in ("confirm_request", "show_widget", "home_updated", "stop_audio", "interrupted"):
                    print(f"  [{kind}] {json.dumps(msg, ensure_ascii=False)[:160]}")
                elif kind == "error":
                    print(f"  ERROR: {msg.get('message')} | {msg.get('detail')}")
                    break
                elif kind == "turn_complete":
                    print(f"  turn complete, tools={msg.get('tools')}")
                    ok = True
                    break
        except TimeoutError:
            print("  timed out waiting for the mascot")
    seconds = len(audio) / 2 / 24000
    print(f"audio: {len(audio)} bytes = {seconds:.1f}s of 24 kHz PCM16")
    if audio:
        OUT.parent.mkdir(exist_ok=True)
        with wave.open(str(OUT), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(bytes(audio))
        print(f"saved: {OUT}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
