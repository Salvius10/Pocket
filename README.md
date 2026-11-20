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

`./make.ps1 test`, `lint`, `typecheck`, `seed-demo`, `web`, `apk` and `l10n` do what they say. `seed-demo` links all six personas and prints their headline numbers next to the planted answer key.

The evals, and what each needs:

| Command | Measures | Needs |
| --- | --- | --- |
| `./make.ps1 eval-insights` | Gate 1: the insight engine against the answer key, 6 personas + 200 eval users | nothing (in memory, about 30 s) |
| `./make.ps1 eval-parsers` | Gate 4: the SMS parser on all 2.4 lakh synthetic SMS; the gate counts the held-out wordings | nothing (about 90 s) |
| `./make.ps1 eval-composer` | The 6 ideal layouts + 30 instruction variants, on the rule-based composer. Add `--model` to run Gemini instead (up to 72 calls) | nothing, or a key with `--model` |
| `./make.ps1 eval-chats` | Gates 2 and 3: the 100 test chats (no buy/sell lines, every number from the ledger) | both services running |

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
- Insight engine (Gate 1): all 520 planted patterns found across the 6 demo personas and the 200 eval users, with 2 extra findings (recall 1.000, precision 0.996).
- SMS parser (Gate 4): 99.98% of the held-out wordings fully correct (30,175 SMS), 99.99% of the seen ones (207,390). The few misses are rows where the answer key lists a balance the SMS does not print. The demo's "add a Swiggy order" writes a synthetic SMS in the user's own bank's wording and puts it through this parser.
- Proposals: every mascot write is a confirm card; only a tap executes, atomically, with an audit row.
- Collab: groups, guests, equal / percent / exact splits, balances, settle plan, UPI link + QR, pot, invite codes.
- Nudges: at most 2 a day, quiet hours, dedupe (in-app).
- Home: 12 catalog widgets, composer (Gemini in live mode; rules in fake mode and whenever the model is unavailable), validator, manual reorder/hide, "Why this layout?". The rule-based composer meets all 30 shipped instruction variants; the Gemini path has produced valid layouts but has not been run through the 30 variants.
- Mascot: painted Poko with 8 moods and lip-sync; text chat everywhere. Live voice runs against `gemini-3.8-live` (checked with typed questions: tool call, spoken answer with the right numbers, refusal on "should I buy this fund"). The browser microphone path has not been tried by a person yet.
- Guardrail: number check and advice check on every transcript sentence, stop-audio and self-correction.
- App: onboarding, five tabs, Profile, English / Hindi / Tamil, offline snapshot with an "as of" time.
- Account-feed (AA) parser: structured fields 100% on 235,963 statement rows, VPA 99.98% where printed; names are the bank's cut-short spelling. The SMS and the account-feed row for the same payment pair up 100% of the time by account, reference, direction and amount.
- Home is drawn by `a2ui_flutter` 0.4.0 from the stored A2UI v1.0 messages; the direct renderer is the fallback. The six default layouts draw identically through both.
- Monthly report (Plan tab): figures, comparison with the month before and the sentences are all computed by core-api.
- Data stays current: for each day after the dataset's last day the synthetic drip repeats that person's own pattern as bank SMS through the parser (on sync, and as a daily job).

Not done yet (see `DECISIONS_LOG.md` for why):

- **Loading through the parsers.** Both parsers are written and measured, but persona link still loads the processed dataset instead of running the account feed through the parser. A reversal SMS is stored but not linked back to the payment it reverses.
- **Gates 2 and 3 on the live model.** `eval-chats` passes both in fake mode; it has not been run against Gemini.
- **Deploy.** `infra/deploy.ps1` has never been run.
- **Android APK.** It builds (`./make.ps1 apk`) but has not been installed on a phone.
- drift (the cache is a snapshot in shared_preferences), the Rive file (H3), Cloud Scheduler set-up and CI.
- Hindi and Tamil strings are agent-written and need a native-speaker review (H4).
