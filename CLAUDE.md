# CLAUDE.md — Rules for building Pocket

You are building the Pocket MVP. Read these three files in this order:

1. `CLAUDE.md` (this file)
2. `ARCHITECTURE.md`, which says what to build
3. `BUILD_PLAN.md`, which says the order and when each part is done

This file wins any conflict.

---

## Non-negotiables

1. **Money is integer paise.** ₹1 = 100 paise. Store money as `bigint` columns named `*_paise`, as `int` in Python and in Dart. Never use floats. Use `Decimal` only for NAV, units, grams and rates. Round half-up.
2. **Code owns every number.** The LLM never adds, subtracts, averages, projects or splits. If the mascot needs a number, add a tool or a tool field that returns it.
3. **No personal investment picks.** The mascot never says buy, sell, switch, redeem or "start a SIP in" a specific fund, stock, ETF, bond, gold product or crypto. It never predicts markets with a call to act. Explaining things the same way for everyone is fine. The user's own numbers are fine.
4. **Pocket never holds money.** Collab tracks who owes whom. Payments happen in the user's own UPI app through a `upi://pay` link or QR. Build no wallet, no payment API and no pooled balance.
5. **Synthetic data only.** The Android manifest has no SMS permissions. Make no real bank or Account Aggregator connections.
6. **Every write needs a tap.** Mascot write tools create a proposal, and only a tap on the confirm card executes it. A spoken "yes" never executes anything.
7. **Safe-to-spend is always the first Home widget** and can't be hidden.
8. **Home uses only the 12 catalog widgets.** Reject any unknown widget type.
9. **At most 2 nudges per user per day, and none in quiet hours.**
10. **No secrets in the repo.** Keep them in `.env` locally (git-ignored) and as Cloud Run environment variables in the cloud (Secret Manager is a later build). Never ship a key inside the app or the web build.
11. **Keep the MVP small.** Demo sign-in (no phone OTP), in-app nudges (no push), Android + web builds. Don't build anything under *Later build* in `ARCHITECTURE.md` §13 unless asked.

---

## Fixed technical choices (don't substitute)

- **Generated UI:** `a2ui_flutter` + `a2ui_core`, A2UI v1.0. **Do not use `genui`, `genui_a2a` or `genui_a2ui`**; all three are discontinued.
- **A2UI carries layout only.** Never put money values in it. Widgets read numbers from the local cache.
- **Models:**

  | Config key | Model | Rules |
  | --- | --- | --- |
  | `MODEL_LIVE` | `gemini-3.8-live` | Audio-only replies; read text from output transcription; no structured output; no `thinking_config` |
  | `MODEL_FLASH` | `gemini-3.8-flash` | Thinking level `low`, never `minimal` |

  Cheap checks also use `MODEL_FLASH` in the MVP (`MODEL_LITE` is a later build). If a model ID is rejected, fail loudly. Never switch models silently.
- **Only the `agent` service calls Gemini.** `core-api` never does.
- **Rive:** `rive` 0.14.x, driven by data binding (View Model `MascotVM`), not state-machine inputs.
- **The guardrail can't pre-screen live speech.** It watches the transcript, stops audio, and makes the mascot correct itself. Prevention comes from tools returning ready-to-speak strings.

## Verify, pin, isolate

`a2ui_flutter`, `a2ui_core`, `rive`, `google-adk`, `google-genai`, `record` and `flutter_pcm_sound` are new or alpha. Your memory of their APIs may be out of date.

- **Before coding against one:** read the installed version's README, its `example/` folder and its public API.
- **Pin exact versions** and commit the lock files (`pubspec.lock`, `uv.lock`).
- **Put each package behind one adapter file** so API changes touch one place:

  | Package | Adapter file |
  | --- | --- |
  | A2UI | `lib/features/home/renderer/a2ui_home_renderer.dart` |
  | Rive | `lib/features/mascot/rive_mascot.dart` |
  | Audio | `lib/core/audio/audio_in.dart`, `audio_out.dart` |
  | Gemini (non-live) | `agent/llm/gemini.py` |
  | ADK live | `agent/live/adk_bridge.py` |

- **Keep a fallback for A2UI and Rive:** a direct Flutter renderer for Home and a `FallbackMascot`, so a package break never kills the demo.

---

## When something isn't specified

Don't stop to ask.

1. Pick the simplest option that keeps the non-negotiables.
2. Add one line to `DECISIONS_LOG.md`: date, area, decision, reason.
3. Keep going.

If you need something only a human can provide (credentials, the Rive file, real SMS samples), use the stub listed in `BUILD_PLAN.md` under *Human tasks* and continue.

---

## Conventions

| Area | Rules |
| --- | --- |
| Python | 3.12; uv workspace; FastAPI; Pydantic v2 (`extra="forbid"` on inputs); SQLAlchemy 2 async + asyncpg; Alembic; ruff; mypy (`--strict` on money and parser code); pytest + hypothesis |
| Flutter | Latest stable; Riverpod 3 without codegen; go_router; drift; dio; freezed + json_serializable; `very_good_analysis` |
| Time | Store UTC; run budget logic in `Asia/Kolkata` |
| IDs | UUIDv4, except fixed slugs (categories, personas, widget types) |
| JSON | `snake_case` on the wire; A2UI component props are `camelCase` (the builder converts) |
| Money in APIs | Always a `Money` object `{paise, display, exact, spoken}` |
| Number format | Indian grouping (₹1,23,456) with Western digits in every language; ASCII `-` for negatives |
| Strings | All user-facing text in ARB files (en, hi, ta); never hard-code it |
| Data access | Every repository call takes `user_id` and filters by it; group data requires membership |
| Logs | Structured JSON; never log phone numbers, transcripts, SMS bodies or tokens |

---

## Definition of done (every task)

1. `make lint`, `make typecheck` and `make test` pass.
2. New logic has tests. Money maths has property tests.
3. If you touched parsers, detectors, the composer, prompts or the guardrail, rerun the matching eval and confirm it still meets its gate.
4. If you changed an API, WebSocket message or LayoutSpec, update `ARCHITECTURE.md` and log the change in `DECISIONS_LOG.md`.
5. No TODO hides broken behaviour.

## Make targets you must provide

`setup` · `dev` · `migrate` · `seed-demo` · `funds` · `sms-variants` · `lint` · `typecheck` · `test` · `eval-parsers` · `eval-insights` · `eval-composer` · `eval-chats` · `app` · `apk`

---

## Don'ts

- Don't let the LLM total two numbers. Add a tool field instead.
- Don't set `response_modalities=["TEXT"]` on the live model.
- Don't show a "Buy", "Invest" or "Start SIP" button anywhere, including on Investments.
- Don't execute a proposal from voice.
- Don't compute totals on the phone. Offline, show the last synced numbers with an "as of" time.
- Don't request SMS permissions "for later".
- Don't call an LLM from `core-api`.
