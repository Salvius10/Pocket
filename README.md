# Pocket

A finance app for India that builds itself around each person. A voice mascot (Poko) builds your Home screen, explains your money in Tamil, Hindi or English, and helps groups share costs. **All data in this build is synthetic.**

Read `CLAUDE.md` (rules), `ARCHITECTURE.md` (what) and `BUILD_PLAN.md` (order) first. Choices made along the way are in `DECISIONS_LOG.md`.

```
apps/mobile          Flutter app: Android + web, one codebase
services/core_api    FastAPI: money maths, ledger, insights, collab, nudges. Never calls an LLM.
services/agent       FastAPI: live voice, UI composer, Pulse, guardrail. Never touches the database.
packages/pocket_common   Money formatting, LayoutSpec validator, A2UI builder, guard core
packages/pocket_synth    Synthetic data generator (shipped with the dataset)
data/                Reference tables, 6 demo personas, test chats, ideal layouts
evals/               Smoke tests and gate evals
infra/               Dockerfiles' build config, deploy script, scheduler jobs
```

## Run it locally

Needs Python 3.12, [uv](https://docs.astral.sh/uv/), Flutter 3.50+, and Postgres 16+ (or leave `DATABASE_URL` empty to use SQLite).

```powershell
copy .env.example .env        # then set DATABASE_URL (create the database "pocket" first)
./make.ps1 setup              # Python deps + flutter pub get      (macOS/Linux: make setup)
./make.ps1 dev                # migrations, then core-api :8080 and agent :8081
./make.ps1 app                # the app in Chrome, pointed at localhost
```

`./make.ps1 test`, `lint`, `typecheck`, `seed-demo`, `eval-chats`, `web`, `apk` and `l10n` do what they say. `seed-demo` links all six personas and prints their headline numbers next to the planted answer key.

With no Gemini key the agent runs in `GEMINI_MODE=fake`: the mascot answers typed questions through the same tools, with no voice. Everything else works.

## When the keys arrive

1. **Gemini key, local.** In `.env` set `GEMINI_API_KEY=...` and `GEMINI_MODE=live`, then restart `make dev`. The Mascot tab shows a mic button; voice is live. Only the agent reads this key.
2. **Check the gates on the real model.** `./make.ps1 eval-chats` runs the 100 test chats: zero buy/sell lines, every spoken number from the ledger, expected-tool recall at least 90%.
3. **Firebase project.** Enable Anonymous sign-in and Hosting, add a Web app, and copy its config values.
4. **Deploy.** `copy infra\demo.env.example infra\demo.env`, fill it in, then `./infra/deploy.ps1`. It builds both images, deploys them to Cloud Run in Mumbai, builds the web app against those URLs and publishes it to Firebase Hosting. `infra/scheduler.sh` adds the daily jobs.

Leave `DATABASE_URL` empty in `infra/demo.env` for the quickest demo: core-api then keeps its data in SQLite inside one always-on instance (it resets if that instance restarts). Point it at Cloud SQL for anything longer-lived.

## What is and isn't built

Working end to end today, verified against the demo data:

- Persona link in about 1 second; Safe-to-spend, pockets, goals, cash flow, bills & EMIs, net worth, investments.
- Insight engine: all 36 planted patterns found across the 6 demo personas with no false positives.
- Proposals: every mascot write is a confirm card; only a tap executes, atomically, with an audit row.
- Collab: groups, guests, equal / percent / exact splits, balances, settle plan, UPI link + QR, pot, invite codes.
- Nudges: at most 2 a day, quiet hours, dedupe (in-app).
- Home: 12 catalog widgets, composer (rules in fake mode, Gemini in live mode), validator, manual reorder/hide, "Why this layout?".
- Mascot: painted Poko with 8 moods and lip-sync; text chat everywhere; the live-voice path is written against google-adk 2.15 but has **not been run against Gemini yet**.
- Guardrail: number check and advice check on every transcript sentence, stop-audio and self-correction.
- App: onboarding, five tabs, Profile, English / Hindi / Tamil, offline snapshot with an "as of" time.

Not done yet (see `DECISIONS_LOG.md` for why):

- **Parsers (M2, Gate 4).** Persona link loads the processed dataset; the AA and SMS parsers are not written.
- **Gate 1 on the 200 eval users.** The detectors are only checked on the 6 demo personas so far.
- **Android APK.** Needs the Android SDK installed; the code has no web-only parts.
- `a2ui_flutter`'s own surface widget is not mounted yet; Home reads the stored A2UI messages through our adapter.
- drift (the cache is a snapshot in shared_preferences), the Rive file (H3), the daily data drip, the monthly report screen, Cloud Scheduler set-up, CI, and widget tests for the app.
- Hindi and Tamil strings are agent-written and need a native-speaker review (H4).
