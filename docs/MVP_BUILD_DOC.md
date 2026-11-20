# Pocket — MVP Build Doc

Nov 20, 2026 · @MellySally

## 1. What we're building

Pocket is a finance app that builds itself around each person. A live voice mascot tells you what it sees in your money and in the world.

| Part | What it does |
| --- | --- |
| **Your app, built for you** | You talk to the mascot and it builds your Home screen. A student, a family and a gig worker each get a different app. |
| **Mascot intelligence** | Your spending patterns, where too much goes, where it could go instead, and what markets and world events mean for your money. Data, not advice. |
| **Collab** | Money with other people: a family budget, a trip pot, flatmates' bills. Shared budget, who paid, who owes, settle up by UPI. |

**Standard features, merged in**

| Standard feature | Where it lives in Pocket | MVP |
| --- | --- | --- |
| Dashboard | Home, built by the mascot | Full |
| Expense and income tracking | Money › one ledger for both | Full |
| Budgeting | Plan › Pockets | Full |
| Savings | Plan › Goals | Full |
| Reports and insights | Mascot › Noticed, plus a monthly report | Full |
| Notifications | Mascot nudges inside the app, at most 2 a day | Full (in-app; push is a later build) |
| EMI and debt tracking | Money › Bills & EMIs | Light: view and reminders |
| Investment tracking | Money › Investments | Light: view only |
| Bank account linking | Money › Accounts | Mock: loads synthetic accounts |

Not in the MVP: real bank linking, payments, and any buy or sell.

**Two lines we don't cross**

| The mascot can say (examples) | The mascot never says |
| --- | --- |
| "Food delivery is ₹8,400 this month, twice your plan." | "Buy this fund." |
| "Move ₹3,000 from Eating out to your Bike goal?" | "Switch your SIP to this one." |
| "Nifty fell 3% this week. Your funds are down ₹2,100." | "Markets will rise. Invest now." |

- **Mascot: data yes, picks no.** Your own numbers, and explanations that are the same for everyone, are fine. A personal pick of a fund, stock or any other security is investment advice, whatever we call it, and needs SEBI registration. \[Likely\] SEBI's definition also covers financial planning, so a fintech lawyer should confirm this line before launch.
- **Collab: track, don't hold.** Money stays in members' own accounts and moves by UPI. Holding a group's pooled money would make Pocket a prepaid wallet, which needs RBI authorisation and ₹5 crore net worth just to apply. \[Certain\]

## 2. Components

We build 13 parts in four groups. Code owns every number; the AI only shapes words and layout.

&#91;embedded content: Pocket component map · 13 parts we build\]

The phone talks to both halves of the backend: code for money, AI for words and layout. The AI touches money only through tools.

| # | Part | Job | Owner |
| --- | --- | --- | --- |
| 1 | Mascot | Rive character with moods and lip-sync; streams your voice live | Mobile |
| 2 | Generated Home | Draws the mascot's layout from a catalog of 12 widgets | Mobile |
| 3 | Fixed screens | Onboarding, Money, Plan, Collab, Profile | Mobile |
| 4 | Offline cache | Last-synced ledger on the phone, so the app opens without a network | Mobile |
| 5 | Core API + ledger | The only place money maths runs; every number on screen comes from here | Backend |
| 6 | Insight engine | Finds patterns in code: overspend, spikes, leaks, idle cash, EMI load | Backend |
| 7 | Collab service | Groups, shared budgets, pots, splits, balances, UPI settle-up links | Backend |
| 8 | Nudge service | Schedules in-app alerts: at most 2 a day, with quiet hours | Backend |
| 9 | Synthetic data generator | Builds every MVP dataset in section 5 | Backend |
| 10 | Mascot agent | Runs the live voice chat and calls tools; never does maths itself | AI |
| 11 | UI composer | Turns what a person needs into a layout; rejects anything outside the catalog | AI |
| 12 | Pulse | Daily digest of markets and world news, with sources, tied to the user's loans and holdings | AI |
| 13 | Guardrail | Blocks personal buy or sell lines; checks every number in a reply against the ledger | AI |

**Widget catalog (12):** Safe-to-spend · Pockets · Goals · Spend by category · Cash flow · Transactions · Bills & EMIs · Net worth · Investments · Insight card · Pulse card · Group pot

**Agent tools:** get\_summary · get\_transactions · get\_insights · get\_pulse · compose\_home · set\_goal · move\_between\_pockets (asks before it moves anything)

**Why the composer is separate:** the Live API can't return structured JSON, so layouts come from a separate Gemini Flash call. \[Certain\]

## 3. The app

Five tabs, with the mascot in the centre. Only Home is generated; the other tabs stay fixed so people always know where things are.

**First run, about 2 minutes**

1. Pick a language (Tamil, Hindi, English) and the mascot's voice.
2. Talk for a minute: what you earn, what you're saving for, what worries you.
3. Link accounts (MVP: picks a synthetic profile).
4. Home builds itself on screen while the mascot explains why.

&#91;embedded content: Generated Homes · 3 personas, same five tabs\]

Every card is a catalog widget, so the mascot can rearrange a Home but never invent a screen.

| Tab | What's in it | Main options |
| --- | --- | --- |
| **Home** (generated) | Safe-to-spend first, then the widgets your life needs | Say "put my EMIs first"; long-press to move or hide; "Why this layout?" |
| **Money** | Transactions (spend and income), Accounts, Bills & EMIs, Investments | Search, filter, add by voice or text, recategorise, split with a group |
| **Mascot** (centre button) | Live voice call, Noticed (your patterns), Pulse (markets and the world) | Talk or type; "show me" opens a widget; turn a tip into a pocket move |
| **Plan** | Pockets (budgets), Goals (savings) | Create by voice; accept the mascot's suggested moves in one tap; pause a pocket |
| **Collab** | Groups: Family, Trip, Flatmates, Custom | Shared budget, a pot with a target, add an expense, split (equal, %, exact), settle by UPI |

**Profile** (avatar, top right): linked accounts · language · mascot voice · notification limits · privacy (export, delete) · disclaimer

**Collab privacy:** each member chooses what a group sees; nothing is shared by default.

**Nudges (in-app):** overspend warning · bill or EMI due · goal reached · group request · weekly report

## 4. Tech stack

Flutter for the app (Android + web), Python agents on Cloud Run in Mumbai, Postgres for money, Gemini for voice and words. Kept small for the MVP.

| Layer | Pick |
| --- | --- |
| App | Flutter: an Android APK for building and testing, plus a web build that judges open from a link |
| Generated screens | `a2ui_flutter` + `a2ui_core`, speaking **A2UI v1.0** (newly released). The older GenUI packages (`genui`, `genui_a2a`, `genui_a2ui`) are discontinued; don't use them |
| Mascot | Rive: a state machine for moods, mouth shapes for lip-sync |
| App plumbing | Riverpod · go\_router · drift (SQLite cache) · fl\_chart |
| Voice | Gemini Live API, native audio (`gemini-3.8-live`): 16 kHz audio in, 24 kHz out, over one WebSocket |
| Agent | Google ADK (Python), bidirectional streaming |
| Words and layouts | `gemini-3.8-flash` for layouts, text and cheap checks |
| Market and world data | Gemini with Google Search grounding · AMFI daily NAV file |
| Backend | Python 3.12 · FastAPI · Pydantic |
| Backend hosting | Cloud Run, Mumbai (asia-south1); keep the agent service warm (min 1 instance) |
| Frontend hosting | Firebase Hosting serves the web build |
| Database | Cloud SQL for PostgreSQL; money stored as integer paise |
| Jobs and alerts | Cloud Scheduler; nudges are shown inside the app |
| Sign-in | Firebase Auth: a "Try a demo persona" button (anonymous sign-in) |
| Settle-up | UPI payment links; money never passes through Pocket |
| Synthetic data | Python · Faker (`en_IN`) · NumPy; Gemini varies the SMS wording |
| Testing | 100 scripted chats on every prompt change · pytest for the maths |
| Build and ship | `gcloud run deploy` from a laptop · web build to Firebase Hosting · APK shared directly · AI Studio and Antigravity · a 2–3 minute demo video as backup |
| Keys | Gemini key as a Cloud Run environment variable, never inside the app |
| Model access | Gemini API for the MVP |

**Later build (after the MVP):** phone OTP sign-in · push notifications (FCM, Cloud Tasks) · Flash-Lite for cheap checks · Secret Manager · CI/CD with GitHub Actions and Artifact Registry · Firebase App Distribution · Gemini Enterprise Agent Platform (formerly Vertex AI) · Gemma 4 on-device SMS parsing · Account Aggregator · Play SMS permission · Play Store · iOS · India data residency (3.8 Flash has no India processing region today)

## 5. Data

The MVP runs on synthetic data in the same formats as the real sources, fed through the real parsers. Going live then means swapping the source, not rewriting the app. No real person's data is in the MVP.

**Personas (6):** student · first-job IT employee · family with a home loan · gig worker · small shop owner · mid-career investor

| Data | Key fields | MVP size | Real source later |
| --- | --- | --- | --- |
| Personas | age band, city, language, income pattern, goals | 6 demo users + 200 test users | Onboarding chat |
| Accounts | bank, type (savings, card, loan, wallet), balance | 2–4 per user | Account Aggregator, in ReBIT's FI schema |
| Transactions | time (IST), amount (paise), debit or credit, mode (UPI, card, cash, NEFT), merchant, UPI ID, category | 12 months; 40–150 a month per user | Bank SMS, Account Aggregator |
| Bank SMS | sender ID, text in each bank's real wording, linked transaction | One per non-cash transaction | Phone inbox, after Play approval |
| Merchants | name, category, UPI ID pattern | About 300 | Our own merchant table |
| Recurring | rent, EMIs (lender, rate, tenure, outstanding), bills, subscriptions | 2–8 per user | Found in transactions; Account Aggregator |
| Holdings | fund name, scheme code, units, SIP amount and date; FDs; gold | 0–8 per user | CAS statement (CAMS, KFintech); Account Aggregator |
| Fund prices | scheme code, date, NAV | **Real:** AMFI daily NAV file | Same |
| Market and world news | date, headline, source link, topic | **Real:** Google Search grounding | Same |
| Pockets and goals | name, monthly limit, target, deadline | 3–6 pockets, 1–3 goals per user | Made in the app |
| Collab groups | type, members, budget, pot target, expenses, splits, settlements | 30 groups: 10 family, 10 trip, 10 flatmates | Made in the app |
| Test chats | user line (Tamil, Hindi, English, Tanglish), expected tools, expected widgets, banned lines | 100 | Real chats, with consent |
| Ideal layouts | persona and its best Home, as A2UI JSON | 6, plus 30 variants | Learned from use |

**Tip:** Finvu's Account Aggregator sandbox accepts test data in ReBIT's schema, so the mock can use a real Account Aggregator flow. \[Likely\]

**Make it realistic**

- Salary lands on the 1st or the last working day; rent by the 5th; EMIs on fixed dates.
- Most payments are small UPI ones (₹20–500), with spikes on weekends, paydays, festivals and sale days.
- Gig income arrives daily and unevenly.
- Add the mess: typos in merchant names, refunds, failed UPI payments, cash withdrawals, transfers between your own accounts.
- **Plant an answer key** in every persona: a forgotten subscription, a price hike, food delivery creeping up 30%, a duplicate charge, idle cash, an expensive card balance.

**The MVP passes when**

- [ ] The insight engine finds at least 9 of every 10 planted patterns.
- [ ] The 100 test chats contain zero personal buy or sell lines.
- [ ] Every number the mascot says matches the ledger.
- [ ] The SMS parser reads at least 95% of synthetic SMS correctly (real SMS will be messier).

## 6. What the user gets

Users stop tracking money by hand and start hearing what their numbers mean, in their own language.

| Today | With Pocket |
| --- | --- |
| Money spread across banks, UPI apps and cards | One picture of every account, filled in automatically |
| Budget apps dropped after a few weeks of manual entry | Tracking is automatic; you just talk |
| One dashboard built for everyone | A Home built for your life |
| You find out you overspent at month-end | A daily safe-to-spend figure, and a warning before it happens |
| Market news that doesn't say what it means for you | What changed this week and what it did to your money, in Tamil, Hindi or English |
| Leaks nobody spots: subscriptions, creeping delivery spend, idle cash | The mascot points them out, with the numbers |
| Trip and flat money tracked in WhatsApp chats | Collab: shared budget, pot, splits and UPI settle-up |
| Apps that earn commissions on what they suggest | Pocket sells no products, so it has no reason to push one |

**What we'll measure in the pilot:** money moved into goals per user per month · share of tips acted on · weekly talk sessions per user

## Sources

- [RBI Master Directions on Prepaid Payment Instruments](https://www.rbi.org.in/scripts/bs_viewmasdirections.aspx?id=12156): non-banks need authorisation; ₹5 crore net worth to apply, ₹15 crore by year three
- [SEBI Investment Advisers Regulations FAQs (ICMAI copy)](https://icmai.in/upload/pd/FAQs-Investment-Advisers-Regulations.pdf): what counts as investment advice, including financial planning; advice in public media is excluded
- [Flutter: updates to A2UI and the GenUI package](https://flutter.dev/blog/new-updates-to-a2ui-and-flutters-genui-package): background on GenUI's earlier A2UI v0.9 support, now superseded by A2UI v1.0
- [pub.dev: genui\_a2ui](https://pub.dev/packages/genui_a2ui): discontinued (as are `genui` and `genui_a2a`)
- [Google Cloud: Gemini Live API overview](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api): gemini-3.8-live is GA and recommended
- [Firebase AI Logic: Live API limits and specs](https://firebase.google.com/docs/ai-logic/live-api/limits-and-specs): audio formats, no structured output, Tamil and Hindi supported
- [Google Cloud: Gemini 3.8 Flash](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-8-flash): GA since 2 Sep 2026; no India processing region
- [AMFI: NAV download](https://www.amfiindia.com/net-asset-value/nav-download): daily NAV reports; history in 90-day pulls
- [Finvu: AA sandbox data API](https://finvu.github.io/sandbox/fip_data_api.html): test data in ReBIT's FI schemas
