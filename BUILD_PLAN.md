# Pocket — Build Plan

Build in this order. Each milestone ends with a **Done when** checklist. Don't start the next milestone until its checklist passes, except where a milestone is marked **parallel**.

Owners: **B** = Backend, **A** = AI, **M** = Mobile. One agent can do all three; the owner tells you which skills the milestone needs.

---

## M0 — Skeleton (B, M)

- Create the monorepo exactly as in `ARCHITECTURE.md` §12.
- Set up docker compose (Postgres 16 + Firebase Auth emulator), the uv workspace, the Flutter app, and Makefile targets: `setup dev migrate seed-demo lint typecheck test eval-parsers eval-insights eval-composer eval-chats app apk web`.
- Write the Alembic migration with every table in `ARCHITECTURE.md` §5, and seed the categories.
- `pocket_common.money` provides `display`, `exact`, `spoken(lang)` and Indian grouping, with 100 shared fixture cases tested in both Python and Dart.
- Set up CI to run lint, typecheck and tests on every push.

**Done when:**
- [ ] `make dev` brings up both services with `/healthz` returning 200
- [ ] Migrations run up and down on a fresh DB
- [ ] Money format fixtures pass in Python and Dart

## M1 — Synthetic data (B)

- `pocket_synth` generates the 6 personas, 200 test users and 30 groups.
- Output files:
  - Account Aggregator–style JSON for each account;
  - bank SMS for each non-cash transaction;
  - recurring items, loans, holdings, pockets, goals, groups;
  - `planted_patterns`.
- Data must follow every realism rule in `ARCHITECTURE.md` §11.
- `make funds` picks about 40 real Direct-Growth schemes from AMFI into `data/funds.csv`, and sets `NIFTY_PROXY_SCHEME_CODE` to a Nifty 50 index fund.
- SMS wording variants are generated once with Gemini (`make sms-variants`) and committed to `data/sms_templates/`. Generation itself never calls an LLM, and it is deterministic for a given seed.

**Done when:**
- [ ] The same seed produces byte-identical output
- [ ] Every user has 40–150 transactions per month over 12 months
- [ ] Each demo persona has all 6 planted patterns
- [ ] Users without a given planted type contain no accidental instance of it (a generator self-check)

## M2 — Parsers and loader (B)

- The AA parser reads JSON and narrations (UPI, NEFT, IMPS, ATM, ACH, POS, interest, card payment) into transactions.
- The SMS parser has per-bank regex families plus a generic fallback. It extracts amount, direction, account last 4, counterparty or VPA, ref no, date and balance.
- The loader:
  - dedupes AA rows against SMS rows by account + ref_no + direction + amount;
  - matches merchants (alias and VPA patterns);
  - assigns categories;
  - links recurring items;
  - pairs own-account transfers;
  - sets the budget month and spend class.
- `POST /v1/onboarding/link {persona_id}` generates and loads a persona for the user in under 8 seconds.

**Done when:**
- [x] `make eval-parsers`: ≥ 95% of synthetic SMS fully correct, run on held-out template variants **(Gate 4)** — 99.98% on 20 Nov 2026 (see DECISIONS_LOG for the method)
- [x] Loader invariants are tested: transfer pairs are symmetric, and failed transactions are excluded (on the feed-loaded ledger and on the shipped one)

As built (20 Nov 2026): persona link loads through the parsers and `ingest/feed.py`. The loader matches merchants, assigns categories, pairs own-account transfers, links reversals, refunds and group payments, and sets the budget month and spend class. It **links** recurring items from a list it is given (the dataset's `recurring_items`, which the dataset marks as a label); it does not detect them. `make eval-loader` on 206 users: with that list every money figure matches the dataset's ledger and category agrees on 93.9% of rows; without it (`--without-bills`) category is 91.1% and the committed / flexible split matches for no user. There is no gate for the loader; details are in `DECISIONS_LOG.md`.

## M3 — Ledger and money maths (B)

- Implement Safe-to-spend, pockets (with adjustments and projection), goals (monthly need, status), cash flow (12 months and 8 weeks), spend by category, net worth, investments (units × NAV, week change), the EMI formula, EMI load, card interest cost, and splits plus the settle plan.
- Public API: summary, transactions (filter, search, recategorise, manual add), accounts, recurring, loans, investments, pockets, goals, proposals (accept/decline with execution), sync, me, settings, export, delete.
- Internal tool endpoints for every agent tool in `ARCHITECTURE.md` §8.

**Done when:**
- [ ] Unit tests pass, including:
  - Safe-to-spend worked example: ₹62,000 income, ₹20,697 committed, ₹10,000 goal reserve, ₹24,100 spent before today, 11 days left → daily allowance **₹650**; with ₹280 spent today → left **₹370**
  - EMI on ₹10,00,000 at 12% over 12 months = **₹88,849**
  - Splits: ₹1,000 split 3 ways equally = 33,334 / 33,333 / 33,333 paise
- [ ] Property tests (Hypothesis) pass: shares always sum to the amount; the settle plan zeroes all balances in at most n−1 payments
- [ ] Accepting a proposal is atomic and writes an audit row

## M4 — Insight engine (B)

- Detectors: overspend_pocket, category_creep, spike, forgotten_subscription, subscription_overlap, price_hike, duplicate_charge, idle_cash, expensive_card_balance, emi_load, pocket_surplus (the "move ₹3,000 to Bike goal" suggestion), goal_off_track, income_drop.
- Each insight stores all of its numbers in `data`, a dedupe `fingerprint`, a severity, an impact, and an optional suggested proposal.
- Ranking: severity first, then money impact. Titles and bodies come from i18n templates, never from the LLM.

**Done when:**
- [x] `make eval-insights`: recall ≥ 0.90 and precision ≥ 0.80 on the six planted types **(Gate 1)** — recall 1.000, precision 0.996 on 206 users, 20 Nov 2026, on the dataset's processed ledger (which carries label columns); recall 0.958, precision 0.994 on a ledger built from the bank feed with no label given to the loader

## M5 — App shell and fixed screens (M) — *parallel with M3–M4 once M2 is done*

- Demo sign-in: a "Try a demo persona" button using Firebase anonymous auth (emulator in local); go_router with 5 tabs (Home, Money, Mascot in the centre, Plan, Collab) and Profile from the avatar.
- drift cache, sync, and an outbox for offline writes.
- Money tab: transactions (search, filter, recategorise, add, split), accounts, bills & EMIs, investments (view only, **no buy buttons**).
- Plan tab: pockets, goals, suggested moves (proposal cards).
- Profile tab: language, voice, notification limits, privacy (export, delete), disclaimer, switch demo profile.
- Strings in ARB files for en/hi/ta.
- The same app builds for Android (`make apk`) and the web (`make web`).

**Done when:**
- [ ] The web build runs in Chrome and Safari (laptop and iPhone)
- [ ] The app opens offline with the last data and an "as of" label
- [ ] All screens show loading, empty and error states
- [ ] Widget tests pass

## M6 — Home widgets and renderer (M)

- Build the 12 widgets as plain Flutter widgets reading from the cache.
- Build the direct renderer (LayoutSpec → widgets) first, then the `a2ui_flutter` renderer with the custom Pocket catalog. Both use the same widget code.
- Long-press to reorder or hide (`PUT /v1/home/manual`). Safe-to-spend can't be moved or hidden.
- "Why this layout?" sheet.

**Done when:**
- [x] The 6 default persona layouts render identically through both renderers (`apps/mobile/test/home_surface_test.dart`)
- [x] Safe-to-spend is pinned at the top

## M7 — UI composer (A)

- `gemini-3.8-flash` structured output → LayoutSpec.
- The validator enforces the rules in `ARCHITECTURE.md` §7.3; one repair retry; then the deterministic default.
- Code builds the A2UI v1.0 messages; `core-api` stores versions; `POST /v1/home/compose` works end to end.

**Done when:**
- [ ] `make eval-composer` on 6 ideal layouts + 30 variants: 100% valid, Safe-to-spend first 100%, constraint match ≥ 80%

## M8 — Live mascot (A, M)

- **Agent:**
  - WebSocket `/v1/live` with the protocol in `ARCHITECTURE.md` §7.1;
  - ADK `run_live` with `gemini-3.8-live`, audio responses only, both transcriptions, session resumption and context compression;
  - all 14 tools;
  - write tools create proposals;
  - turns are logged to `chat_turns`;
  - onboarding mode asks 4 questions (how money comes in, roughly how much, saving for what, what worries you), then calls `save_profile`.
- **Phone:**
  - mic stream (16 kHz PCM16, echo cancellation on) and speaker stream (24 kHz); on the web, a Web Audio player for the speaker stream;
  - `interrupted` and `stop_audio` flush playback;
  - lip-sync from playback RMS mapped to the Rive `mouthOpen` value;
  - moods: idle, listening, thinking, talking, happy, concerned, celebrating, sleepy;
  - transcript view, text input box and mute-voice toggle;
  - confirm cards for proposals;
  - `show_widget` sheets.
- **Rive:** use `assets/rive/mascot.riv` with View Model `MascotVM` { `mood` enum, `mouthOpen` 0–100, `blink` trigger, `lookX`/`lookY` −1..1 }. Until the designer's file arrives, use a `FallbackMascot` (CustomPainter) with the same interface.

**Done when:**
- [ ] A spoken question → tool call → spoken answer with correct numbers on a real Android phone, and in a laptop browser, with first audio in under 1.5 s after the user stops talking
- [ ] Accepting a proposal by tap updates the Home numbers
- [ ] Saying "yes" executes nothing

## M9 — Guardrail and chat evals (A)

- Live transcript monitor (number check + advice check), stop-audio, correction injection, `guard_events`.
- Text guard for written AI text (no digits; advice check).
- `data/test_chats/chats.jsonl` with 100 chats:
  - by language: 40 English, 25 Tamil, 20 Hindi, 15 Tanglish;
  - by topic: 30 spending, 15 layout changes, 15 advice-bait, 10 markets, 10 collab, 10 pockets/goals, 10 misc;
  - each chat lists expected tools, expected widgets and banned patterns.
- `eval_chats.py` sends each user line as text input to the live session and evaluates the output transcription and tool calls.

**Done when:**
- [ ] `make eval-chats`:
  - **zero** personal buy/sell lines **(Gate 2)**
  - **every** number the mascot says matches the ledger **(Gate 3)**
  - expected-tool recall ≥ 90%
  - If Gate 3 fails, fix the tools or prompts; don't loosen the check.

## M10 — Pulse and market data (A, B) — *parallel with M9*

- AMFI ingest runs nightly; history is backfilled (a synthetic walk anchored to the real NAV if AMFI history is unreachable).
- Nifty weekly % is computed from the index-fund NAV.
- Pulse build:
  1. a grounded Gemini call (Google Search) returns news text and sources;
  2. a structuring call returns up to 8 items in en/hi/ta;
  3. items without a source URL are dropped;
  4. the guardrail runs on the summaries.
- Personal links are computed in code. Examples: MF week change in ₹; the EMI change for a 0.25% rate move on a floating home loan.

**Done when:**
- [ ] The Pulse tab shows today's items with sources and "what it means for you" lines whose numbers come from code

## M11 — Collab (B, M)

- Create groups, invite by 6-character code or deeplink `pocket://join/<code>`, add guests.
- Shared budget, pot with target and deadline, add expense with equal / % / exact split.
- Split a transaction from the Money tab; the user's spend then counts only their share.
- Balances and settle plan; UPI link + QR + copy UPI ID; payment status flow: pending → link_opened → marked_paid → confirmed.
- Per-member privacy settings.

**Done when:**
- [ ] Two real phones can share a trip group and settle ₹1 via UPI
- [ ] Guest expenses work
- [ ] Nothing personal is visible to a group without opt-in

## M12 — Nudges and reports (B, M)

- The planner: priority order bill_due > overspend > group_request > goal_reached > weekly_report > insight; max 2 a day; quiet hours (postponed to quiet end); dedupe; shown **inside the app** (a nudge card on Home and a list in Mascot › Noticed). No push.
- Weekly "Week in review" card; monthly report screen. The LLM summary uses placeholders only.

**Done when:**
- [ ] A test proves a third nudge on the same day is suppressed
- [ ] A test proves a nudge scheduled at 23:00 moves to 08:00

## M13 — Onboarding, demo and ship (all)

- First run:
  1. language → "Try a demo persona" sign-in → voice;
  2. talk for about 1 minute;
  3. pick a persona (the closest match is preselected);
  4. Home builds on screen widget by widget while the mascot explains why.
- Demo tools: switch persona, daily drip, `POST /internal/jobs/demo/inject` presets (e.g. "Swiggy order now", which triggers an overspend nudge).
- Deploy both services to Cloud Run (asia-south1) with `gcloud run deploy --source .`, set up Scheduler jobs, deploy the web build to Firebase Hosting, and share the APK file directly.
- Record a 2–3 minute demo video of the critical path below: the backup if live voice fails, and the place to show push-style nudges.

**Done when:**
- [ ] A judge opens the Firebase Hosting link and reaches a generated Home in under 3 minutes, with no install
- [ ] A new user goes from install to a generated Home in under 3 minutes
- [ ] All four gates pass on the deployed environment

---

## The four MVP gates

| Gate | Measure | Pass |
| --- | --- | --- |
| 1 | Insight engine on planted patterns | recall ≥ 0.90, precision ≥ 0.80 |
| 2 | 100 test chats | 0 personal buy/sell lines |
| 3 | 100 test chats | every spoken number matches the ledger |
| 4 | SMS parser on synthetic SMS | ≥ 95% fully correct |

## Demo critical path (if time runs short, protect this first)

1. Onboarding talk, then Home builds itself
2. "Where is my money going?" → spoken answer with numbers
3. Noticed: food delivery up 30% → "Move ₹3,000 from Eating out to Bike goal?" → tap → Home updates
4. "Should I buy this fund?" → safe refusal, plus how the user's own funds moved
5. Trip group → split → settle by UPI

## Human tasks (stub these, never block on them)

| # | Task | Stub until done |
| --- | --- | --- |
| H1 | Create the GCP project (billing, APIs) and Firebase project; turn on anonymous sign-in and Hosting | Local docker + Auth emulator |
| H2 | Gemini API key as an environment variable on the Cloud Run `agent` service | `GEMINI_MODE=fake` with canned responses |
| H3 | Rive mascot file built to the `MascotVM` contract | `FallbackMascot` |
| H4 | Native-speaker review of Tamil and Hindi strings, the guard lexicon and the test chats | Agent-written translations marked `x-review` |
| H5 | A few real (redacted) bank SMS samples to check the templates | Agent-written templates |
| H6 | Gold price value (`GOLD_PRICE_PER_GRAM_PAISE`) | Placeholder labelled "approx." |
| H7 | Fintech lawyer confirms the "data, not advice" line before public launch | n/a for MVP |
| H8 | Check the Buildathon submission rules: live link, APK or video only | Ship all three |

## Later build (after the MVP)

Cut from the MVP to keep it simple; the full list is in `ARCHITECTURE.md` §13.

- **LB1 — Real sign-in:** Firebase phone OTP (register `in.pocket.mvp`, SHA-1, test numbers) replaces the demo button.
- **LB2 — Push nudges:** FCM, a `devices` table and Cloud Tasks for timed delivery, on top of the in-app nudges.
- **LB3 — Ops:** Secret Manager, GitHub Actions deploys with Workload Identity Federation, Artifact Registry, Firebase App Distribution.
- **LB4 — Cheaper checks:** move guardrail and number checks to `gemini-3.5-flash-lite`.
- **LB5 — Going live:** Gemini Enterprise Agent Platform, Gemma 4 on-device SMS parsing, real Account Aggregator, Play SMS permission, Google Play Store, iOS, India data residency.
