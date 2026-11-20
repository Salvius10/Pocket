"""The only file that touches Google ADK live (google-adk 2.15.0, verified 20 Nov 2026).

Bridges one phone session to `gemini-3.8-live` through `Runner.run_live` + `LiveRequestQueue`:
audio-only replies, text read from output transcription, input transcription on, session
resumption and context compression on, no thinking_config. Tools call core-api through the
session, which also feeds the guardrail's allowed-number set.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from agent.config import get_settings
from agent.live.session import LiveSession
from agent.mascot.tools import TOOL_SPECS
from agent.prompts.lines import LANGUAGE_NAMES, ONBOARDING_PROMPT, SYSTEM_PROMPT

log = logging.getLogger("agent.adk")

VOICES = {"warm": "Aoede", "bright": "Puck", "calm": "Charon", "clear": "Kore"}
LANG_CODES = {"en": "en-IN", "hi": "hi-IN", "ta": "ta-IN"}
ONBOARDING_TOOLS = ("save_profile",)


def _trim(out: dict[str, Any]) -> dict[str, Any]:
    """What the model gets back: the ready-to-speak line first, then the facts behind it."""
    result = out.get("result")
    text = out.get("say") or ""
    payload: dict[str, Any] = {"say": text}
    if out.get("error"):
        payload["error"] = out["error"]
    if isinstance(result, dict):
        slim = {k: v for k, v in result.items() if k not in ("holdings", "items", "months", "weeks", "last_month", "breakdown")}
        for key in ("items", "holdings"):
            if isinstance(result.get(key), list):
                slim[key] = result[key][:5]
        payload["facts"] = slim
    return payload


def _make_tools(session: LiveSession, names: tuple[str, ...] | None) -> list[Any]:
    from google.adk.tools.base_tool import BaseTool
    from google.genai import types

    class CoreTool(BaseTool):
        def __init__(self, spec: dict[str, Any]) -> None:
            super().__init__(name=spec["name"], description=spec["description"])
            self._spec = spec

        def _get_declaration(self) -> Any:
            return types.FunctionDeclaration(name=self._spec["name"], description=self._spec["description"],
                                             parameters_json_schema=self._spec["parameters"])

        async def run_async(self, *, args: dict[str, Any], tool_context: Any) -> Any:
            await session.mood("thinking")
            return _trim(await session.call_tool(self._spec["name"], dict(args or {})))

    return [CoreTool(s) for s in TOOL_SPECS if names is None or s["name"] in names]


class AdkBridge:
    def __init__(self, session: LiveSession) -> None:
        self.s = session
        self._queue: Any = None
        self._task: asyncio.Task[None] | None = None
        self._got_partial = False
        self._spoke = False  # the mascot produced audio or text in the current turn
        self._settle: asyncio.Task[None] | None = None

    async def start(self) -> None:
        from google.adk.agents import LlmAgent
        from google.adk.agents.run_config import RunConfig, StreamingMode  # type: ignore[attr-defined]
        from google.adk.live.live_request_queue import LiveRequestQueue
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        settings = get_settings()
        os.environ["GOOGLE_API_KEY"] = settings.gemini_api_key
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"
        s = self.s
        onboarding = s.mode == "onboarding"
        language = LANGUAGE_NAMES.get(s.lang, "English")
        instruction = (ONBOARDING_PROMPT.format(language=language) if onboarding else SYSTEM_PROMPT.format(
            language=language, pockets=", ".join(s.names.get("pockets", [])) or "none", goals=", ".join(s.names.get("goals", [])) or "none"))
        agent = LlmAgent(name="poko", model=settings.model_live, instruction=instruction,
                         tools=_make_tools(s, ONBOARDING_TOOLS if onboarding else None))
        runner = InMemoryRunner(agent=agent, app_name="pocket")
        await runner.session_service.create_session(app_name="pocket", user_id=s.user_id, session_id=s.session_id)
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=[types.Modality.AUDIO],  # audio only: text comes from output transcription
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICES.get(s.voice, settings.live_voice_default))),
                language_code=LANG_CODES.get(s.lang, "en-IN"),
            ),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            session_resumption=types.SessionResumptionConfig(),
            # Must name the sliding window: an empty config passes setup, then gemini-3.8-live rejects
            # the first message with "1007 invalid argument" (found 20 Nov 2026).
            context_window_compression=types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()),
        )
        self._queue = LiveRequestQueue()
        self._task = asyncio.create_task(self._pump(runner, run_config))
        if onboarding:
            self._send_text("Start the conversation: greet me and ask the first question.")

    def _send_text(self, text: str) -> None:
        from google.genai import types

        self._queue.send_content(types.Content(role="user", parts=[types.Part(text=text)]))

    async def _pump(self, runner: Any, run_config: Any) -> None:
        s = self.s
        try:
            async for event in runner.run_live(user_id=s.user_id, session_id=s.session_id, live_request_queue=self._queue, run_config=run_config):
                if getattr(event, "error_code", None):
                    raise RuntimeError(f"{event.error_code}: {getattr(event, 'error_message', '')}")
                if event.interrupted:
                    self._got_partial = False
                    self._spoke = False
                    await s.interrupted()
                    continue
                tin = event.input_transcription
                if tin is not None and tin.text:
                    await s.user_said(tin.text, final=bool(tin.finished))
                    if tin.finished:
                        await s.mood("thinking")
                tout = event.output_transcription
                if tout is not None and tout.text:
                    self._spoke = True
                    if event.partial:
                        self._got_partial = True
                        await s.mascot_text(tout.text)
                    elif not self._got_partial:
                        await s.mascot_text(tout.text)  # only a final arrived: use it once
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        blob = part.inline_data
                        if blob is not None and blob.data and (blob.mime_type or "").startswith("audio/"):
                            self._spoke = True
                            await s.mood("talking")
                            await s.send_audio(blob.data)
                if event.turn_complete:
                    self._got_partial = False
                    if s.turn_tools and not self._spoke:
                        # gemini-3.8-live ends a turn when it issues a tool call and starts another to
                        # speak the answer. For the phone that is still one turn, so wait for the speech
                        # (with a deadline, in case a tool like show_widget needs no words).
                        self._arm_settle()
                        continue
                    await self._finish_turn()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # fail loudly: tell the phone, never fall back to another model
            log.exception("live session failed")
            await s.send("error", message=f"Live voice failed: {type(exc).__name__}", detail=str(exc)[:300])
            await s.mood("sleepy")

    def _arm_settle(self) -> None:
        if self._settle is not None:
            self._settle.cancel()

        async def later() -> None:
            await asyncio.sleep(12)
            if not self._spoke:
                await self._finish_turn()

        self._settle = asyncio.create_task(later())

    async def _finish_turn(self) -> None:
        if self._settle is not None and self._settle is not asyncio.current_task():
            self._settle.cancel()
        self._settle = None
        self._spoke = False
        await self.s.turn_complete()

    async def on_text(self, text: str) -> None:
        await self.s.user_said(text)
        await self.s.mood("thinking")
        self._send_text(text)

    async def on_audio(self, pcm: bytes) -> None:
        from google.genai import types

        self._queue.send_realtime(types.Blob(data=pcm, mime_type="audio/pcm;rate=16000"))

    async def on_audio_end(self) -> None:
        self._queue.send_audio_stream_end()

    async def correct(self, instruction: str) -> None:
        self._send_text(f"[SYSTEM CORRECTION, do not read this aloud] {instruction}")

    async def close(self) -> None:
        if self._settle is not None:
            self._settle.cancel()
        if self._queue is not None:
            self._queue.close()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: S110 - shutting down
                pass
