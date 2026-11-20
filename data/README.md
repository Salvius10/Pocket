# Pocket synthetic data (v1)

This is fake money data for Pocket, built to look like real Indian banking. It covers 6 demo personas and 200 evaluation users, from **1 Nov 2025 to 19 Nov 2026** (IST). It includes bank statements in Account Aggregator format, bank SMS in each bank's own style, and an answer key of planted insights. Every person, employer, landlord and school is invented. Brands are real.

> **Paise:** every money column is an integer in paise (₹1 = 100 paise) and ends in `_paise`. Example: `34900` = ₹349.

---

## 1. Read this first

1. **The time window is fixed.** ARCHITECTURE.md §7.5 and §11 ask for two things this generator doesn't do yet:
   - "generate fresh with `end_date` = yesterday";
   - a daily drip of new transactions.

   The data is current up to 19 Nov 2026 and goes stale after that. Moving the window means changing about 90 hard-coded dates (see §8). **[Certain]**
2. **SMS wording is modelled, not copied.** Templates follow each bank's public alert formats, but they were not checked against a corpus of real SMS. Test your parser on 50–100 real, redacted SMS before you trust its accuracy score. **[Likely close, not verified]**
3. **Fund NAV history is synthetic.** Only the latest NAV of each scheme is real (AMFI, 18–19 Nov 2026). The earlier days are a random walk that ends on that real value.
4. **Simplifications:**
   - Card interest is charged only on the unpaid amount. Real Indian cards charge from each purchase date once you miss paying in full, so real charges are **higher**.
   - Auto-sweep FDs are never broken early.
   - There is no gold price, only grams.
   - Festival dates are approximate.
5. **Never build a payment link from a ledger UPI ID.** Ledger IDs use real handles (`@okaxis`, `@ybl`, `@paytm`), so a generated ID could belong to a real stranger. Only group members' `@pocketdemo` IDs are safe for links. No bank routes that handle.

---

## 2. What's inside

| Path | What | Format |
| --- | --- | --- |
| `load_demo.sql`, `load_eval.sql` | Load everything into Postgres (§3) | SQL for `psql` |
| `DATA_DICTIONARY.md` | Every table and column: type, role, meaning, example | Markdown |
| `validation_report.md` | Realism stats and integrity checks from the last build | Markdown |
| `reference/` | Categories (38), merchants (325), banks (7), cities (15), festivals, 16 real mutual funds, NAV history | CSV |
| `demo/db/` | The 6 demo personas, already processed: 21 tables | CSV |
| `demo/sources/<persona>/` | The raw inputs for the same personas: `account_aggregator/*.json` (one per account) and `sms.jsonl` | JSON / JSONL |
| `demo/groups.json` | The 6 demo groups as nested JSON (members, expenses, shares, settlements) | JSON |
| `demo/demo_personas.xlsx` | For people to browse. **Not a data source.** | Excel |
| `eval/db/` | The 200 evaluation users: same tables, no SMS table, no profile facts | CSV |
| `eval/sources/` | `sms.jsonl.gz` (230,122 SMS) and `account_aggregator.jsonl.gz` (one statement per line) | gzip JSONL |
| `content/` | `test_chats.jsonl` (100 mascot test chats: 40 English, 22 Tamil, 20 Hindi, 18 Tanglish), `ideal_layouts.json` (6), `layout_variants.json` (30), `widget_catalog.json` (12 widgets) | JSON |
| `generator/` | The code that made all of this (§8) | Python |

| | Demo | Eval |
| --- | --- | --- |
| People | 6 | 200 (35 student, 40 first job, 40 family, 30 gig, 20 shop, 35 investor) |
| Accounts | 18 | 550 |
| Transactions | 7,379 | 228,584 |
| Bank SMS | 7,443 | 230,122 |
| Groups | 6 | 30 (10 family, 10 trip, 10 flatmates) |
| Planted patterns | all 6 types in every persona | 137 users get 1–6 types; 63 get none |

---

## 3. Load into Postgres

```bash
cd pocket-synthetic-data                  # the folder holding this README
psql "$DATABASE_URL" -f load_demo.sql      # reference + demo, under a second
psql "$DATABASE_URL" -f load_eval.sql      # eval, about 2 seconds; unzip the eval zip into this same folder first
```

- **Schemas:**
  - `synth_ref` holds `reference/`.
  - `synth_demo` holds `demo/db/`.
  - `synth_eval` holds `eval/db/`.

  Table and column names match the CSVs exactly. Re-running is safe: each table is dropped and reloaded inside one transaction.
- **Load check:** each script ends with a row-count table, and every row should show `ok = t`. Tested on Postgres 16: 46 tables, all counts matched.
- `\copy` reads files on the machine running `psql`. If Postgres is in Docker, either run `psql` on your machine or mount this folder into the container.
- Timestamps are stored in UTC. Show them in IST with `occurred_at AT TIME ZONE 'Asia/Kolkata'`.

**Mapping into the app tables (ARCHITECTURE.md §5)** with `INSERT … SELECT`:

| App table | From | Notes |
| --- | --- | --- |
| `users`, `profile_facts` | `users`, `profile_facts` | `firebase_uid` etc. are set when a persona is linked |
| `accounts` | `accounts` | `balance_paise` ← `current_balance_paise` |
| `transactions` | `transactions` | `merchant` ← `merchant_key`; `category` ← `category_id`; `recurring_item_id` ← join `recurring_items` on (`user_id`, `recurring_key` = `key`). **Compute `budget_month`, `personal_amount_paise` and `spend_class` in code.** They are not in the data. |
| `sms_messages` | `sms_messages` | `parse_status` and `parse_result` come from your parser |
| `merchants`, `categories` | `synth_ref.*` | |
| `recurring_items` | `recurring_items` | map `kind` with the table below; compute `next_due_date` |
| `loans`, `holdings`, `nav_prices` | `loans`, `holdings`, `synth_ref.nav_history_synthetic` | |
| `pockets`, `goals`, `goal_contributions` | same names | |
| `groups` … `group_invites` | same names | |
| `planted_patterns` | `planted_patterns` | the answer key; `insights` is what your detectors write |

| Data `recurring_items.kind` | App kind |
| --- | --- |
| `subscription` | subscription |
| `bill`, `recharge`, `lpg`, `milk`, `fees`, `maid` (household help paid by UPI), `remittance` (money sent home) | bill |
| `rent`, `emi`, `insurance` | same |
| `sip`, `ppf` | sip |

`transactions.mode`:
- `upi`, `card`, `neft`, `imps`, `atm` and `cash` map directly.
- `nach` = NACH/ECS auto-debit (EMIs, SIPs, insurance).
- `autopay` = UPI AutoPay mandate (subscriptions).
- `interest` and `other` → other.

---

## 4. Two ways to use it

**Demo (what you show):** load `demo/db` as the already-processed state. That is the fastest path. The more honest path matches ARCHITECTURE.md §11: feed `demo/sources/<persona>/` (AA JSON + SMS) through your real parsers and categoriser. `demo/db` is then the expected output.

**Evaluation (what you score):** feed `eval/sources/` through the same pipeline and compare against the labels. Every column has a **role** in `DATA_DICTIONARY.md`:

| Role | Meaning | Rule |
| --- | --- | --- |
| `obs` | A real bank feed or SMS gives you this | Parsers and detectors may read it |
| `label` | Ground truth | **Never** pass it to what you are evaluating |
| `app` | State the app or user creates | Load it as setup |
| `ref` | Reference data | Load it |

The labels are:
- in `transactions`: `category_id`, `merchant_key`, `kind`, `status`, `recurring_key`, `transfer_pair_id`, `reversal_of_id`, `refund_of_id`, `sms_ids`, `planted_pattern`;
- in `sms_messages`: `template_id`, `holdout`, `transaction_id`, `ground_truth`;
- the whole of `recurring_items` and `planted_patterns`;
- `users.planted_types` and `accounts.role`.

**SMS parser gate (BUILD_PLAN Gate 4):** score only rows with `holdout = true` (30,175 SMS across demo and eval). Those wordings appear nowhere else, so a parser can't pass by memorising templates. `ground_truth.kind = ignore` marks OTPs, promos and statement notices, which the parser must skip.

---

## 5. Conventions

- **Money:** integer paise, always positive. `transactions.direction` gives the sign.
- **Cards:** the balance is the amount owed. A `debit` is a new charge (the amount owed goes up); a `credit` is a payment or refund.
- **Times:** ISO 8601 with `+05:30`. Every date is an IST date.
- **Running balance:** sort an account's rows by `occurred_at` (ties keep file order), and each `balance_after_paise` = the previous one ± `amount_paise`. This holds for all 235,963 rows.
- **IDs:** deterministic UUIDs. The same code always gives the same IDs.
- **Lists in a cell:** `|`-separated, unless the dictionary says comma-separated.
- **Empty cell:** NULL.
- **Reference numbers:**
  - A UPI RRN is 12 digits: the year's last digit + day of year + hour + 6 digits. Example: `530519071383` = 2025, day 305, 19:00.
  - A NEFT UTR is the bank code + `N` + yy + day of year + 6 digits.

---

## 6. The answer key

`planted_patterns` has one row per planted pattern. The rows that form it also carry `transactions.planted_pattern`. Each type fills its own columns (see the dictionary).

| Type | What was planted | How it is defined (use this rule to score) | `natural_key` |
| --- | --- | --- | --- |
| `forgotten_subscription` | A ₹1–₹2 mandate check at sign-up, a 7- or 30-day trial, then full monthly charges for a service the user never mentions | ≥3 full charges after a ≤₹5 mandate debit from a subscription merchant | `forgotten_sub:{merchant_key}` |
| `price_hike` | A fixed bill, plan or subscription goes up once in October 2026; the first charge at the new price lands between 5 Oct and 14 Nov 2026 | latest charge (within the last 45 days) ≥10% and ≥₹20 above the median of the 3 before it. Variable bills (electricity, gas), rent, EMIs and SIPs never count. | `price_hike:{merchant_key}:{new_amount_paise}` |
| `category_creep` | Food delivery rises (measured +26% to +56%, median +36%) | average of Aug–Oct 2026 ≥ +25% over the average of May–Jul 2026 | `creep:food_delivery:2026-11` |
| `duplicate_charge` | The same order charged twice | same account, merchant and amount, both `success`, within 10 minutes | `dup:{second_txn_id}` |
| `idle_cash` | Money parked in a savings account that is barely used | idle = lowest end-of-day balance in the last 60 days − 1.5 × the account's average monthly outflow (last 3 complete months), rounded down to ₹1,000. Flag if idle ≥ max(₹25,000, 0.5 × outflow). | `idle:{account_id}:2026-11` |
| `expensive_card_balance` | Card bills paid only partly, so finance charges + 18% GST get posted | any `fin_charge` row in the window | `card_revolve:{account_id}:2026-11` |

**Negatives are checked too.** Applying these exact rules to users without that pattern finds **0** accidental hits for every type (see `validation_report.md`). So a detector built on these rules should score 100% recall with no false positives. If yours flags extra cases, compare its rule with the one above.

**Demo answer key:**

| Persona | Forgotten subscription | Price hike | Food delivery creep | Duplicate charge | Idle cash | Card finance charges |
| --- | --- | --- | --- | --- | --- | --- |
| Karthik (student, Chennai, ta) | Spotify ₹59/month, 8 charges | Jio Prepaid ₹299 → ₹349 | +37% | Swiggy ₹382 | SBI ••8920: ₹47,000 | KOTAK ••1654: ₹419.23 paid in charges |
| Ananya (first_job, Bengaluru, en) | Audible ₹199/month, 9 charges | Spotify ₹119 → ₹139 | +38% | Uber ₹447 | HDFC ••9168: ₹1,03,000 | ICICI ••4602: ₹2,181.76 paid in charges |
| Lakshmi (family, Chennai, ta) | ZEE5 ₹99/month, 8 charges | Airtel Xstream Fiber ₹942.82 → ₹1,060.82 | +32% | BigBasket ₹317 | SBI ••7605: ₹1,56,000 | HDFC ••3757: ₹1,908.72 paid in charges |
| Rahul (gig, Delhi, hi) | JioSaavn ₹99/month, 10 charges | Jio Prepaid ₹349 → ₹399 | +40% | Zomato ₹244 | SBI ••8564: ₹66,000 | SBI ••1125: ₹251.29 paid in charges |
| Sunita (shop, Jaipur, hi) | Sony LIV ₹299/month, 7 charges | Airtel ₹529.82 → ₹588.82 | +34% | Blinkit ₹284 | AXIS ••9553: ₹3,05,000 | HDFC ••6443: ₹1,847.09 paid in charges |
| Vikram (investor, Mumbai, en) | LinkedIn Premium ₹1,567/month, 10 charges | Netflix ₹649 → ₹749 | +45% | Uber ₹228 | KOTAK ••4004: ₹4,42,000 | AXIS ••1500: ₹8,294.56 paid in charges |

Idle cash is the rounded `idle_paise`. Card charges are the total finance charges + GST paid so far.

---

## 7. What makes it realistic

**Money in:**
- Salary arrives on the last working day, the first working day or a fixed date, depending on the employer. A fixed date that falls on a Sunday, a 2nd/4th Saturday or a bank holiday moves to the working day before.
- Gig payouts come in daily and weekly, uneven in size.
- Shop owners get daily UPI sales, pay suppliers by NEFT, and draw money for the household.
- Students get pocket money from parents, plus family top-ups when they run short.

**Money out:**
- UPI dominates. For the median user, 76% of debits are UPI, and 75% of UPI debits are under ₹500.
- Neighbourhood shops are paid through QR codes (`gpay-…@okbizaxis`, `paytmqr…@paytm`).
- Brands appear under their legal names in narrations (Swiggy as `BUNDL TECHNOLOGIES`, Zomato as `ETERNAL LIMITED`, Blinkit as `BLINK COMMERCE`).
- Rent and household help are paid by UPI to people.
- EMIs and SIPs go out by NACH. Subscriptions go by UPI AutoPay or card. Card bills are paid through CRED or BillDesk.

**Bank-side rows:**
- Quarterly savings interest, worked out on daily balances.
- SMS alert charges and the debit card annual fee.
- ATM withdrawals beyond the free monthly limit cost ₹23 + 18% GST = ₹27.14.
- Auto-sweep FDs book surplus balance on the 6th.
- Card statements carry a 5% minimum due and finance charges + 18% GST.
- No-cost EMIs and floating-rate home loans.

**Mess a real feed has:**
- About 1.5% of merchant UPI payments of ₹50 or more fail and get reversed, then are retried.
- Refunds are full or partial and go back to the account the money came from.
- Merchant names come with typos (`ZOMTO`, `SWIGY`).
- OTPs, promos and statement notices mixed into the SMS.
- 7 banks' different narration and SMS styles, multi-line SMS, and DLT sender headers (`AX-HDFCBK-S`).

**Seasons:**
- Spending rises around Diwali, the festive e-commerce sales, New Year and regional festivals (Pongal, Onam, Navratri, Chhath and others).
- Summer electricity bills peak. They are variable, so they are **not** price hikes.
- Flat renters get a mid-year rent increment of 5–8%.

**Integrity:** these are all zero in `validation_report.md`:
- broken running balances;
- duplicate IDs;
- SMS pointing at a missing transaction;
- one-sided transfers;
- refunds bigger than the purchase;
- card statements whose charges don't reconcile;
- negative bank balances.

---

## 8. Rebuild or change it

```bash
cd generator
pip install -r requirements.txt                              # numpy, openpyxl (pinned)
python -m pocket_synth.export --out ../out                    # about 30 s; writes everything plus validation_report.md
python -m pocket_synth.sqlgen ../out                          # load_demo.sql, load_eval.sql
python -m pocket_synth.docs ../out                            # DATA_DICTIONARY.md
```

- **Same code, same files:** with the same Python and numpy versions, two runs produce byte-identical files, except the `.xlsx`, which records when it was saved (BUILD_PLAN: "the same seed produces byte-identical output"). Tested on Python 3.13 with numpy 2.5.3; `requirements.txt` pins both libraries. Python 3.10+ is needed.
- **Modules:**
  - `refdata.py`: banks, merchants, cities, festivals, funds, window.
  - `personas.py`, `population.py`: who the people are and what is planted.
  - `engine.py`: the day-by-day ledger simulation.
  - `render.py`: narrations, SMS, AA JSON.
  - `groups.py`: collab.
  - `content.py`: chats and layouts.
  - `export.py`: tables, answer key, validation.
- **To move the window** (needed for "fresh with `end_date` = yesterday"):
  1. Change `START`/`END`, `FESTIVALS` and `BANK_HOLIDAYS` in `refdata.py`, and the sale windows in `engine.py` (`_season`).
  2. Make the planted dates relative to `END`: about 90 literal 2025/2026 dates in `population.py`, `groups.py`, `personas.py` and `engine.py`.
  3. Rebuild. Check that `validation_report.md` still shows every planted signal present, 0 accidental signals and all integrity checks at 0.
- **For a daily drip:** don't regenerate the history every day. Build once with `END` some months ahead, then release one day of rows and SMS at a time. Re-running with a new `END` changes the random draws, so the history would change too.
