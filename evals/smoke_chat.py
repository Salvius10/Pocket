"""Smoke test over HTTP + WebSocket: link a persona, then talk to the mascot (needs `make dev` running).

Run: uv run python evals/smoke_chat.py [persona] [lang]
"""

from __future__ import annotations

import asyncio
import json
import sys

import httpx
import websockets

CORE, AGENT = "http://127.0.0.1:8080", "ws://127.0.0.1:8081"
LINES = {
    "en": ["hi", "How much can I spend today?", "Where is my money going?", "How much have I spent on food delivery this month?",
           "Can I afford a 3,000 rupee dinner this weekend?", "What did you notice?", "yes", "Should I buy this fund?",
           "Will the market go up next month?", "Put my bills first", "What's happening in the markets?", "How is the trip group doing?"],
    "ta": ["இன்று எவ்வளவு செலவு செய்யலாம்?", "என் பணம் எங்கே போகுது?", "இந்த ஃபண்ட் வாங்கலாமா?", "நீங்கள் என்ன கவனித்தீர்கள்?"],
    "hi": ["आज कितना खर्च कर सकता हूँ?", "मेरा पैसा कहाँ जा रहा है?", "कौन सा फंड खरीदूँ?", "आपने क्या देखा?"],
}


async def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    persona = sys.argv[1] if len(sys.argv) > 1 else "first_job"
    lang = sys.argv[2] if len(sys.argv) > 2 else "en"
    dev_user = f"chat-{persona}-{lang}"
    headers = {"X-Dev-User": dev_user}
    async with httpx.AsyncClient(base_url=CORE, headers=headers, timeout=60) as http:
        await http.patch("/v1/me", json={"language": lang})
        r = await http.post("/v1/onboarding/link", json={"persona_id": persona})
        r.raise_for_status()
        print("linked:", r.json()["linked"], "| home:", [w["type"] for w in r.json()["home"]["spec"]["widgets"]])
        r = await http.post("http://127.0.0.1:8081/internal/jobs/pulse", headers={"X-Internal-Token": "local-internal-token"})
        print("pulse job:", r.json())
    async with websockets.connect(f"{AGENT}/v1/live") as ws:
        await ws.send(json.dumps({"type": "hello", "dev_user": dev_user, "lang": lang, "voice": "warm", "mode": "chat"}))
        print("<<", json.loads(await ws.recv()))
        for text in LINES.get(lang, LINES["en"]):
            print(f"\nYOU: {text}")
            await ws.send(json.dumps({"type": "text", "text": text}))
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=40))
                kind = msg["type"]
                if kind == "transcript" and msg["role"] == "mascot" and msg["final"]:
                    print(f"POKO: {msg['text']}")
                elif kind in ("confirm_request", "show_widget", "home_updated", "stop_audio", "error"):
                    extra = msg.get("proposal", {}).get("title") or msg.get("widget", {}).get("type") or \
                        [w["type"] for w in msg.get("home", {}).get("spec", {}).get("widgets", [])] or msg.get("reason") or msg.get("message")
                    print(f"  [{kind}] {extra}")
                elif kind == "turn_complete":
                    print(f"  tools: {msg['tools']}")
                    break


if __name__ == "__main__":
    asyncio.run(main())
