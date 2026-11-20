"""The only file that talks to Gemini for non-live calls (google-genai 2.34, verified 20 Nov 2026).

MODEL_FLASH runs at thinking level `low` (never `minimal`).

Model rules:
- A rejected model id or a bad request raises as-is. We fail loudly and never pick another model.
- If MODEL_FLASH is *unavailable* (overloaded, timing out) and MODEL_FLASH_FALLBACK is set, that
  one named model is used instead, with a warning in the log every time and `last_model` saying
  which model answered. Nothing is substituted unless the operator configured it.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from agent.config import get_settings

log = logging.getLogger("agent.gemini")
PRIMARY_PAUSE_SECONDS = 90.0  # after MODEL_FLASH fails, go straight to the fallback for this long
UNAVAILABLE_CODES = {429, 500, 502, 503, 504}


class GeminiError(RuntimeError):
    pass


def _is_unavailable(exc: Exception) -> bool:
    """True for capacity and timeout failures; False for anything that means our request is wrong."""
    import httpx

    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError, TimeoutError)):
        return True
    code = getattr(exc, "code", None)
    return isinstance(code, int) and code in UNAVAILABLE_CODES


class Gemini:
    def __init__(self) -> None:
        from google import genai
        from google.genai import types

        s = get_settings()
        if not s.gemini_api_key:
            raise GeminiError("GEMINI_API_KEY is not set")
        # Someone is waiting on these calls. One try, twelve seconds at most (the API refuses deadlines
        # under 10 s; the SDK default keeps retrying for about 30 s on a 503), so callers can fall back.
        self._client = genai.Client(
            api_key=s.gemini_api_key,
            http_options=types.HttpOptions(timeout=12_000, retry_options=types.HttpRetryOptions(attempts=1)),
        )
        self._model = s.model_flash
        self._fallback = s.model_flash_fallback if s.model_flash_fallback != s.model_flash else ""
        self._primary_down_until = 0.0
        self.last_model = self._model

    @property
    def used_fallback(self) -> bool:
        return self.last_model != self._model

    def _config(self, **kw: Any) -> Any:
        from google.genai import types

        return types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW), **kw)

    async def _generate(self, contents: str, config: Any) -> Any:
        models = [self._model, *([self._fallback] if self._fallback else [])]
        if self._fallback and time.monotonic() < self._primary_down_until:
            models = [self._fallback]
        last: Exception | None = None
        for model in models:
            try:
                resp = await self._client.aio.models.generate_content(model=model, contents=contents, config=config)
            except Exception as exc:
                if not _is_unavailable(exc):
                    raise  # wrong model id, bad request, auth: fail loudly
                last = exc
                if model == self._model:
                    self._primary_down_until = time.monotonic() + PRIMARY_PAUSE_SECONDS
                    log.warning("MODEL_FLASH %s is unavailable (%s). %s", model, type(exc).__name__,
                                f"Using MODEL_FLASH_FALLBACK {self._fallback}." if self._fallback else "No fallback model is configured.")
                else:
                    log.warning("MODEL_FLASH_FALLBACK %s is unavailable too (%s).", model, type(exc).__name__)
                continue
            self.last_model = model
            return resp
        raise GeminiError("the model is unavailable right now") from last

    async def generate_json(self, prompt: str, schema: dict[str, Any], system: str | None = None) -> Any:
        """Structured output: the reply is parsed JSON matching `schema`."""
        resp = await self._generate(prompt, self._config(system_instruction=system, response_mime_type="application/json", response_json_schema=schema))
        try:
            return json.loads(resp.text or "")
        except json.JSONDecodeError as exc:
            raise GeminiError("model did not return JSON") from exc

    async def grounded(self, prompt: str) -> tuple[str, list[dict[str, str]]]:
        """Google Search grounding. Returns the text and the web sources it used."""
        from google.genai import types

        resp = await self._generate(prompt, self._config(tools=[types.Tool(google_search=types.GoogleSearch())]))
        sources: list[dict[str, str]] = []
        for cand in resp.candidates or []:
            meta = cand.grounding_metadata
            for chunk in (meta.grounding_chunks if meta and meta.grounding_chunks else []):
                if chunk.web and chunk.web.uri:
                    sources.append({"url": chunk.web.uri, "title": chunk.web.title or "", "domain": chunk.web.domain or ""})
        return resp.text or "", sources

    async def judge(self, question: str) -> bool:
        """Cheap yes/no check (borderline guard sentences)."""
        out = await self.generate_json(question, {"type": "object", "properties": {"answer": {"type": "boolean"}}, "required": ["answer"]})
        return bool(out.get("answer"))


_gemini: Gemini | None = None


def gemini() -> Gemini:
    global _gemini
    if _gemini is None:
        _gemini = Gemini()
    return _gemini
