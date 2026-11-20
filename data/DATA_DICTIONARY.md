# Data dictionary

Generated from the CSVs by `python -m pocket_synth.docs`; every column is listed. Types are what `load_*.sql` creates.

**Role** column: `obs` = a real bank feed or SMS gives you this, so parsers and detectors may read it; `label` = ground truth, never shown to what you are evaluating; `app` = state the app or user creates; `ref` = reference data.

Lists inside a cell are `|`-separated unless the column says comma-separated. Empty cell = NULL.

## Reference (`reference/`, schema `synth_ref`)

### `banks`

The 7 banks whose statement and SMS styles are modelled. (7 rows; primary key: bank_code)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `bank_code` | text | ref | Short code, e.g. `HDFC`, `SBI`. | HDFC |
| `name` | text | ref | Bank name. | HDFC Bank |
| `ifsc_prefix` | text | ref | First 4 letters of every IFSC of this bank. | HDFC0 |
| `sms_sender_codes` | text | ref | 6-letter SMS sender codes used for account alerts (pipe-separated). | HDFCBK |
| `card_sms_sender_codes` | text | ref | Sender codes used for credit card alerts (pipe-separated). | HDFCBK |
| `savings_rate_bps_approx` | bigint | ref | Approximate savings interest rate, basis points (275 = 2.75% a year). | 275 |
| `account_number_length` | bigint | ref | Digits in this bank's savings account numbers. | 14 |

### `categories`

The fixed category slugs. `default_class` is the spend class before recurring detection. (38 rows; primary key: category_id)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `category_id` | text | label | Category slug (`synth_ref.categories`). | salary |
| `kind` | text | ref | `income`, `refund`, `transfer`, `saving` or `expense`. | income |
| `default_class` | text | ref | Spend class before recurring detection: `income`, `refund`, `transfer`, `saving`, `committed`, `flexible`. A transaction linked to a recurring bill or subscription becomes `committed`. | income |
| `name_en` | text | ref | English label. | Salary |

### `cities`

The 15 cities personas live in, with local price anchors. (15 rows; primary key: city)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `city` | text | ref | City name. | Chennai |
| `state` | text | ref | State. | TN |
| `region` | text | ref | `south`, `north`, `west` or `east` (drives festivals and names). | tamil |
| `power_board` | text | ref | Electricity board. | tneb |
| `power_billing` | text | ref | `monthly` or `bimonthly` billing. | bimonthly |
| `petrol_per_litre_approx` | numeric | ref | Approximate petrol price, ₹ per litre. | 100.8 |
| `lpg_cylinder_approx` | bigint | ref | Approximate 14.2 kg LPG cylinder price, ₹. | 868 |
| `metro` | text | ref | Whether the city has a metro rail system. | cmrl |
| `areas` | text | ref | Neighbourhoods used for personas (pipe-separated). | Velachery\|Anna Nagar\|Tambaram\|Madip… |

### `festivals`

Festival and sale windows that lift spending, with per-category multipliers. (24 rows; primary key: name, start_date)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `name` | text | ref | Festival or sale. | Guru Nanak Jayanti |
| `start_date` | date | ref | First day of the spending window. | 2025-11-05 |
| `end_date` | date | ref | Last day of the spending window. | 2025-11-05 |
| `regions` | text | ref | Regions it applies to (pipe-separated); `*` = everywhere. | hindi |
| `spend_multipliers` | jsonb | ref | JSON: category → spending multiplier during the window. | {"eating_out": 1.3} |

### `funds`

16 real mutual fund schemes with their real latest NAV from AMFI. (16 rows; primary key: scheme_code)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `scheme_code` | integer | ref | AMFI scheme code. | 120716 |
| `scheme_name` | text | ref | Scheme name as AMFI lists it. | UTI Nifty 50 Index Fund - Direct Plan … |
| `category` | text | ref | Fund category. | index |
| `latest_nav` | numeric | ref | Real NAV on `latest_nav_date`. | 179.7634 |
| `latest_nav_date` | date | ref | Date of that NAV. | 2026-11-19 |
| `latest_nav_source` | text | ref | Where the NAV was read. | AMFI via mfapi.in, checked 20 Nov 2026 |

### `merchants`

Merchants: real brands plus invented neighbourhood shops. (325 rows; primary key: merchant_key)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `merchant_key` | text | label | Merchant slug (`synth_ref.merchants`). | swiggy |
| `name` | text | ref | Brand name shown in the app. | Swiggy |
| `narration_name` | text | ref | Name as it usually appears in bank narrations (often the legal entity, e.g. `BUNDL TECHNOLOGIES` for Swiggy). | SWIGGY |
| `category_id` | text | label | Category slug (`synth_ref.categories`). | food_delivery |
| `subcategory` | text | ref | Finer label. | ott |
| `vpa_pattern` | text | ref | UPI ID the merchant collects on; `{n}` is replaced by digits per store. | swiggyorders@axisbank |
| `cities` | text | ref | Cities where it operates (pipe-separated); `*` = everywhere. | * |
| `is_subscription_likely` | boolean | ref | True for services usually paid monthly. | False |
| `is_local` | boolean | ref | True for invented neighbourhood shops (tea stalls, kirana, medical stores). | False |
| `aliases` | text | ref | Other spellings seen in narrations, including typos (pipe-separated). | SWIGGY\|SWIGGY LIMITED\|BUNDL TECHNOLO… |

### `nav_history_synthetic`

Daily NAVs for the window. Only the last value per scheme is real (`source = amfi`). (4,752 rows; primary key: scheme_code, nav_date)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `scheme_code` | integer | ref | AMFI scheme code (`synth_ref.funds`). | 120716 |
| `nav_date` | date | ref | Date. | 2025-09-17 |
| `nav` | numeric | ref | NAV on that date. | 173.5579 |
| `source` | text | ref | `amfi` (real, last day only) or `synthetic_backfill`. | synthetic_backfill |

## Demo and eval (`demo/db/` → `synth_demo`, `eval/db/` → `synth_eval`)

### `accounts`

Bank accounts and credit cards. (demo 18 rows · eval 550 rows; primary key: account_id)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `account_id` | text | app | UUID (stable: the same seed always gives the same id) | 77fcc7ce-a3cf-5d4b-865b-5c6566bdb311 |
| `user_id` | text | app | Owner (`users.user_id`). | c282e400-dfa4-5c9d-9175-1f6089c85555 |
| `role` | text | label | Generator's role for the account: `primary`, `secondary`, `card`, `business`. Not something a bank reports. | primary |
| `provider` | text | app | `synthetic` (in production: the Account Aggregator data provider). | synthetic |
| `institution_code` | text | obs | Bank code (`synth_ref.banks`). | KOTAK |
| `institution_name` | text | obs | Bank name. | Kotak Mahindra Bank |
| `type` | text | obs | `savings`, `current` or `credit_card`. | savings |
| `masked_number` | text | obs | Masked number as banks show it; length follows the bank's real account-number length (cards: 16). | XXXXXX6596 |
| `ifsc` | text | obs | Branch IFSC (4-letter bank code + `0` + 6 characters). Empty for cards. | KKBK0009374 |
| `nickname` | text | app | User's name for the account. | Scholarship account |
| `opened_on` | date | obs | Account opening date. | 2024-12-12 |
| `opening_balance_paise` | bigint | obs | Balance at the start of `data_start`, before the first transaction. Cards: amount owed. | 320000 |
| `current_balance_paise` | bigint | obs | Balance at 23:59:59 IST on `data_end`. Cards: amount owed. | 36996 |
| `balance_as_of` | timestamptz | obs | Time of `current_balance_paise`. | 2026-11-19T23:59:59+05:30 |
| `credit_limit_paise` | bigint | obs | Card limit. Empty for bank accounts. | 1500000 |
| `interest_rate_bps` | bigint | obs | Yearly rate in basis points. Savings: interest earned (275 = 2.75%). Cards: finance charge (4320 = 43.2% a year, 3.6% a month). | 275 |
| `statement_day` | bigint | obs | Card statement day of month. | 12 |
| `due_day` | bigint | obs | Card payment due day of month (about 20 days after the statement). | 4 |

### `balance_snapshots`

End-of-day balance (IST) of every savings and current account, every day of the window. (demo 4,608 rows · eval 148,224 rows; primary key: account_id, as_of_date)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `account_id` | text | app | Account (`accounts.account_id`). | 77fcc7ce-a3cf-5d4b-865b-5c6566bdb311 |
| `as_of_date` | date | obs | Day (IST). | 2025-11-01 |
| `balance_paise` | bigint | obs | Balance at the end of that day. | 920000 |

### `card_statements`

Monthly credit card statements. (demo 77 rows · eval 2,085 rows; primary key: account_id, statement_date)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `account_id` | text | app | Account (`accounts.account_id`). | 13cbddbb-6311-56a6-874f-969b6fba78a5 |
| `user_id` | text | app | Owner (`users.user_id`). | c282e400-dfa4-5c9d-9175-1f6089c85555 |
| `statement_date` | date | obs | Statement date. | 2025-11-12 |
| `due_date` | date | obs | Payment due date (20 days later). | 2025-12-02 |
| `total_due_paise` | bigint | obs | Total amount due. | 185000 |
| `min_due_paise` | bigint | obs | Minimum due: 5% of the total, at least ₹200 (the whole total if smaller). | 20000 |
| `paid_paise` | bigint | obs | Paid before the due date. Empty = due date is after `data_end`. | 185000 |
| `finance_charges_paise` | bigint | obs | Finance charges plus 18% GST billed on this statement. | 0 |
| `revolving_after_due_paise` | bigint | obs | Unpaid amount carried past the due date. Empty = paid in full. | 77500 |
| `finance_charges_next_paise` | bigint | obs | Charges (with GST) that this statement's unpaid amount caused; billed on the next statement. | 3292 |

### `goal_contributions`

Money earmarked to goals, one row per month. (demo 207 rows · eval 2,000 rows; primary key: none)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `goal_id` | text | app | Goal (`goals.goal_id`). | a8e6fc1b-c723-5bb3-a531-37b7b8be864e |
| `user_id` | text | app | Owner (`users.user_id`). | c282e400-dfa4-5c9d-9175-1f6089c85555 |
| `amount_paise` | bigint | app | Amount in paise (₹1 = 100). Always positive. | 600002 |
| `month` | date | app | Month (first day). | 2026-05-01 |
| `source` | text | app | `loader`. | loader |
| `note` | text | app | `Already saved at setup` or `Monthly`. | Already saved at setup |

### `goals`

Savings goals. (demo 12 rows · eval 200 rows; primary key: goal_id)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `goal_id` | text | app | Goal (`goals.goal_id`). | a8e6fc1b-c723-5bb3-a531-37b7b8be864e |
| `user_id` | text | app | Owner (`users.user_id`). | c282e400-dfa4-5c9d-9175-1f6089c85555 |
| `name` | text | app | Display name. | Laptop |
| `emoji` | text | app | Display emoji. | 💻 |
| `target_paise` | bigint | app | Target amount. | 6500000 |
| `deadline` | date | app | Target date; empty = none. | 2027-06-30 |
| `monthly_plan_paise` | bigint | app | Planned monthly saving; empty = none. | 50000 |
| `priority` | bigint | app | 1 = the user's main goal. | 0 |
| `status` | text | app | Lifecycle status. | active |
| `created_by` | text | app | Who created the row (`loader` = seeded with the data). | loader |
| `created_at` | date | app | When it was created. | 2026-05-01 |
| `saved_paise` | bigint | app | Sum of `goal_contributions` up to `data_end`. | 1200000 |

### `group_expense_shares`

Who owes what for each expense. Shares always sum exactly to the expense. (demo 1,584 rows · eval 7,965 rows; primary key: expense_id, member_id)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `expense_id` | text | app | Group expense (`group_expenses.expense_id`). | a9c8e4b8-4e31-56a8-a0f8-86cad5d2e74b |
| `member_id` | text | app | Group member (`group_members.member_id`). | e9dcf4f6-f0dd-526a-b33f-0423da54742a |
| `share_paise` | bigint | app | This member's share. | 100000 |

### `group_expenses`

Shared expenses entered in a group. (demo 504 rows · eval 2,139 rows; primary key: expense_id)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `expense_id` | text | app | Group expense (`group_expenses.expense_id`). | a9c8e4b8-4e31-56a8-a0f8-86cad5d2e74b |
| `group_id` | text | app | Group (`groups.group_id`). | 49fac755-4f57-50c5-bbca-a58b1552e6b0 |
| `paid_by_member_id` | text | app | Who paid. | dc75f547-51fd-5ee0-acc2-42f4a827edde |
| `amount_paise` | bigint | app | Amount in paise (₹1 = 100). Always positive. | 500000 |
| `description` | text | app | What the user typed. | Homestay advance (White Town) |
| `category_id` | text | app | Category slug (`synth_ref.categories`). | travel |
| `occurred_at` | timestamptz | app | When. | 2026-11-10T16:12:26+05:30 |
| `split_method` | text | app | `equal`, `percent` or `exact`. | equal |
| `split_input` | jsonb | app | JSON the user entered: `{member_ids}` (equal), `{percent: {member: pct}}`, or `{paise: {member: paise}}` (exact). | {"member_ids": ["e9dcf4f6-f0dd-526a-b3… |
| `linked_transaction_id` | text | app | The payer's bank or card transaction, when the payer is a synthetic user. | a3fa4582-102d-571f-b94a-54732e07e48b |
| `created_by_member_id` | text | app | Who entered it. | dc75f547-51fd-5ee0-acc2-42f4a827edde |
| `is_deleted` | boolean | app | Soft delete flag. | False |

### `group_invites`

Invite codes for joining a group. (demo 6 rows · eval 30 rows; primary key: code)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `group_id` | text | app | Group (`groups.group_id`). | 49fac755-4f57-50c5-bbca-a58b1552e6b0 |
| `created_by` | text | app | `users.user_id` of the creator. | c282e400-dfa4-5c9d-9175-1f6089c85555 |
| `max_uses` | bigint | app | How many people can join with it. | 10 |
| `code` | text | app | 6-character invite code. | PPGWFH |
| `expires_at` | date | app | Expiry date. | 2026-10-27 |
| `uses` | bigint | app | Times used. | 0 |

### `group_members`

People in each group. Guests are not Pocket users. (demo 22 rows · eval 116 rows; primary key: member_id)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `member_id` | text | app | UUID (stable: the same seed always gives the same id) | e9dcf4f6-f0dd-526a-b33f-0423da54742a |
| `group_id` | text | app | Group (`groups.group_id`). | 49fac755-4f57-50c5-bbca-a58b1552e6b0 |
| `user_id` | text | app | Pocket user, if the member is one; empty for guests. | c282e400-dfa4-5c9d-9175-1f6089c85555 |
| `display_name` | text | app | Name shown in the group (invented). | Karthik Ramasamy |
| `vpa` | text | app | UPI ID for settle-up links. Always `@pocketdemo`, a handle no bank routes. | karthik.ramasamy@pocketdemo |
| `role` | text | app | `owner` or `guest`. | owner |
| `join_order` | bigint | app | 0 = owner. In equal splits the leftover paise go to the lowest `join_order` first. | 0 |
| `sharing` | jsonb | app | JSON: what this member shares with the group (`category_ids`, `show_transactions`, `goal_ids`). | {"category_ids": [], "show_transaction… |

### `group_pot_contributions`

Money members put into a group's shared pot (for a trip). (demo 24 rows · not in eval; primary key: id)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `group_id` | text | app | Group (`groups.group_id`). | 49fac755-4f57-50c5-bbca-a58b1552e6b0 |
| `id` | text | app | UUID (stable: the same seed always gives the same id) | 9df21cb2-cb55-5a67-961e-788d9893564b |
| `member_id` | text | app | Group member (`group_members.member_id`). | e9dcf4f6-f0dd-526a-b33f-0423da54742a |
| `amount_paise` | bigint | app | Amount in paise (₹1 = 100). Always positive. | 150000 |
| `method` | text | app | `upi`. | upi |
| `note` | text | app | Free-text note. | For Pondy |
| `occurred_at` | timestamptz | app | When. | 2026-11-10T19:49:05+05:30 |

### `groups`

Collab groups: trips, flatmates, families. (demo 6 rows · eval 30 rows; primary key: group_id)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `group_id` | text | app | Group (`groups.group_id`). | 49fac755-4f57-50c5-bbca-a58b1552e6b0 |
| `key` | text | app | Template key, e.g. `demo_student`. | demo_student |
| `type` | text | app | `trip`, `flatmates` or `family`. | trip |
| `name` | text | app | Display name. | Pondy trip |
| `emoji` | text | app | Display emoji. | 🏖️ |
| `owner_user_id` | text | app | Creator (`users.user_id`). | c282e400-dfa4-5c9d-9175-1f6089c85555 |
| `created_at` | date | app | When it was created. | 2026-10-20 |
| `budget_monthly_paise` | bigint | app | Shared monthly budget; empty = none. | 900000 |
| `pot_target_paise` | bigint | app | Shared pot target (trips). | 1600000 |
| `pot_deadline` | date | app | Pot deadline. | 2026-12-15 |
| `status` | text | app | Lifecycle status. | active |

### `holdings`

Mutual funds, fixed deposits, gold, PPF and EPF. (demo 35 rows · eval 1,483 rows; primary key: none)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `user_id` | text | app | Owner (`users.user_id`). | 914b3ba0-dff9-566f-919d-c3b66de91b72 |
| `kind` | text | obs | `mutual_fund`, `fd`, `gold`, `ppf` or `epf`. | mutual_fund |
| `name` | text | obs | Scheme, deposit or account name. | UTI Nifty 50 Index Fund - Direct Plan … |
| `scheme_code` | integer | obs | AMFI code (`synth_ref.funds`). Mutual funds only. | 120716 |
| `units` | numeric | obs | Units held at `data_end`. | 266.28 |
| `invested_paise` | bigint | obs | Total invested. | 4800000 |
| `sip_amount_paise` | bigint | obs | Monthly SIP. | 300000 |
| `sip_day` | bigint | obs | SIP debit day. | 10 |
| `folio_masked` | text | obs | Masked folio number. | XXXX205/43 |
| `platform` | text | obs | Order platform (`BSE StAR MF`, `NSE NMF II`). | BSE StAR MF |
| `fd_principal_paise` | bigint | obs | FD amount. | 1000000 |
| `fd_rate_bps` | bigint | obs | FD rate, basis points a year. | 650 |
| `fd_start_date` | date | obs | FD booking date. | 2025-11-06 |
| `fd_maturity_date` | date | obs | FD maturity date. | 2026-11-06 |
| `gold_grams` | numeric | obs | Grams of gold. No gold price is included. | 20.0 |
| `balance_paise` | bigint | obs | PPF/EPF balance. | 48500000 |
| `balance_as_of` | date | obs | Date of that balance (31 March statement). | 2026-03-31 |
| `booked_by` | text | obs | `sweep` = the bank's auto-sweep moved surplus into an FD; `user` = booked by hand. | sweep |
| `latest_nav` | numeric | obs | Real latest NAV. | 179.7634 |
| `latest_nav_date` | date | obs | Its date. | 2026-11-19 |
| `value_at_latest_nav_paise` | bigint | obs | `units × latest_nav`, in paise. | 4786740 |

### `loans`

Loans whose EMIs appear in the ledger. (demo 5 rows · eval 125 rows; primary key: user_id, key)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `user_id` | text | app | Owner (`users.user_id`). | ef24f3be-39c4-58ad-9f99-4207acb7e427 |
| `key` | text | app | Stable slug, unique per user. | home_loan |
| `lender` | text | obs | Lender. | SBI Home Loan |
| `loan_type` | text | obs | `home`, `vehicle`, `consumer_durable`, `business`. | home |
| `rate_type` | text | obs | `fixed` or `floating`. | floating |
| `principal_paise` | bigint | obs | Amount borrowed. | 480000000 |
| `outstanding_paise` | bigint | obs | Principal still owed at `data_end`. | 411167540 |
| `interest_rate_bps` | bigint | obs | Yearly rate in basis points (815 = 8.15%). | 815 |
| `tenure_months` | bigint | obs | Total EMIs. | 240 |
| `emi_paise` | bigint | obs | Monthly EMI. | 4059800 |
| `emi_day` | bigint | obs | Day of month the EMI is debited. | 5 |
| `start_date` | date | obs | First EMI date (can be before the window). | 2021-04-05 |
| `end_date` | date | obs | Last EMI date. | 2041-03-05 |
| `emis_paid` | bigint | obs | EMIs paid up to `data_end`, including those before the window. | 68 |
| `months_left` | bigint | obs | EMIs still to pay. | 172 |
| `zero_cost_emi` | boolean | obs | True = no-cost EMI (0% interest, principal split evenly). | False |

### `planted_patterns`

The answer key: insights the app must find. One row per planted pattern. (demo 36 rows · eval 484 rows; primary key: user_id, natural_key)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `user_id` | text | app | Owner (`users.user_id`). | c282e400-dfa4-5c9d-9175-1f6089c85555 |
| `pattern_type` | text | label | `forgotten_subscription`, `price_hike`, `category_creep`, `duplicate_charge`, `idle_cash`, `expensive_card_balance`. | forgotten_subscription |
| `natural_key` | text | label | Stable key a detector's output can be matched on (format per type in the README). | forgotten_sub:spotify |
| `merchant_key` | text | label | Merchant involved (subscription, price hike, duplicate). | spotify |
| `mandate_txn_id` | text | label | Forgotten subscription: the ₹1–₹2 mandate check debit at sign-up. | 9361c1ae-a87f-5e0c-8d31-7bcaf8796482 |
| `mandate_date` | date | label | Forgotten subscription: sign-up date. | 2026-03-02 |
| `mandate_amount_paise` | bigint | label | Forgotten subscription: mandate check amount. | 100 |
| `first_charge_date` | date | label | Forgotten subscription: first full charge after the free trial. | 2026-04-01 |
| `monthly_amount_paise` | bigint | label | Forgotten subscription: monthly charge. | 5900 |
| `charges` | bigint | label | Forgotten subscription: full charges so far. | 8 |
| `total_paid_paise` | bigint | label | Forgotten subscription: total paid so far. | 47200 |
| `account_id` | text | label | Account involved. | 77fcc7ce-a3cf-5d4b-865b-5c6566bdb311 |
| `recurring_key` | text | label | Recurring item involved. | recharge |
| `old_amount_paise` | bigint | label | Price hike: old price. | 29900 |
| `new_amount_paise` | bigint | label | Price hike: new price. | 34900 |
| `first_new_charge_date` | date | label | Price hike: first charge at the new price. | 2026-10-29 |
| `latest_txn_id` | text | label | Price hike: latest charge. | fbc9bfd8-7c89-5c97-abef-549917ff5d48 |
| `increase_pct` | bigint | label | Price hike or creep: rise in whole percent. | 17 |
| `category_id` | text | label | Creep: category (`food_delivery`). | food_delivery |
| `earlier_months` | text | label | Creep: the 3 baseline months (comma-separated `YYYY-MM`). | 2026-05,2026-06,2026-07 |
| `recent_months` | text | label | Creep: the 3 recent months. | 2026-08,2026-09,2026-10 |
| `earlier_avg_paise` | bigint | label | Creep: monthly average in the baseline months. | 291933 |
| `recent_avg_paise` | bigint | label | Creep: monthly average in the recent months. | 399433 |
| `this_month_to_date_paise` | bigint | label | Creep: spend so far in the current month. | 281300 |
| `first_txn_id` | text | label | Duplicate: the genuine charge. | b4937237-5d11-5de0-8308-445552bb4d7d |
| `second_txn_id` | text | label | Duplicate: the repeat charge. | 878de09e-6665-516e-8d25-f3333331fc7c |
| `amount_paise` | bigint | label | Duplicate: amount charged twice. | 38200 |
| `first_at` | timestamptz | label | Duplicate: time of the first charge. | 2026-11-13T12:20:16+05:30 |
| `second_at` | timestamptz | label | Duplicate: time of the second (within 10 minutes). | 2026-11-13T12:22:19+05:30 |
| `both_posted` | boolean | label | Duplicate: both charges are in the ledger. | true |
| `account_masked` | text | label | Idle cash: masked account number. | XXXXXXX8920 |
| `bank` | text | label | Bank code. | SBI |
| `min_balance_60d_paise` | bigint | label | Idle cash: lowest end-of-day balance in the last 60 days. | 4762217 |
| `avg_monthly_outflow_paise` | bigint | label | Idle cash: this account's average monthly outflow over the last 3 complete months. | 590 |
| `buffer_paise` | bigint | label | Idle cash: 1.5 × that outflow, kept as a safety buffer. | 885 |
| `idle_paise` | bigint | label | Idle cash: minimum balance − buffer, rounded down to ₹1,000. | 4700000 |
| `threshold_paise` | bigint | label | Idle cash: flag only if idle ≥ max(₹25,000, 0.5 × outflow). | 2500000 |
| `flagged` | boolean | label | Idle cash: passed the threshold. | true |
| `definition` | text | label | Idle cash: the rule in words. | idle = min end-of-day balance over las… |
| `card_masked` | text | label | Card balance: masked card number. | XXXXXXXXXXXX1654 |
| `monthly_rate_bps` | bigint | label | Card balance: monthly finance-charge rate (360 = 3.6%). | 360 |
| `finance_charge_txn_ids` | text | label | Card balance: finance charge and GST rows (comma-separated). | 0a4e20bb-5ee1-5c3b-8380-d7a4ecb5c8fe,5… |
| `finance_charges_paise` | bigint | label | Card balance: total finance charges + GST paid. | 41923 |
| `last_charge_date` | date | label | Card balance: latest finance charge. | 2026-11-12 |
| `outstanding_at_end_paise` | bigint | label | Card balance: amount owed at `data_end`. | 1057223 |
| `revolving_statements` | text | label | Card balance: statements not paid in full (comma-separated `YYYY-MM`). | 2026-09,2026-10,2026-11 |

### `pockets`

Monthly budget envelopes the user set up. (demo 33 rows · eval 891 rows; primary key: pocket_id)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `pocket_id` | text | app | UUID (stable: the same seed always gives the same id) | 0176f7dc-e58c-54db-8b44-ce69b395e067 |
| `user_id` | text | app | Owner (`users.user_id`). | c282e400-dfa4-5c9d-9175-1f6089c85555 |
| `name` | text | app | Display name. | Food delivery |
| `emoji` | text | app | Display emoji. | 🍔 |
| `monthly_limit_paise` | bigint | app | Monthly budget. | 250000 |
| `category_ids` | text | app | Categories this pocket covers (pipe-separated). | food_delivery |
| `status` | text | app | Lifecycle status. | active |
| `sort_order` | bigint | app | Display order. | 0 |
| `created_by` | text | app | Who created the row (`loader` = seeded with the data). | loader |
| `created_at` | date | app | When it was created. | 2026-06-01 |

### `profile_facts`

What each demo persona told the mascot at onboarding, in their own language. Demo only. (demo 30 rows · not in eval; primary key: user_id, key)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `user_id` | text | app | Owner (`users.user_id`). | c282e400-dfa4-5c9d-9175-1f6089c85555 |
| `key` | text | app | `occupation`, `income`, `saving_for`, `worries` or `household`. | occupation |
| `value` | text | app | What they said, in their language. | B.Com இரண்டாம் ஆண்டு மாணவன் |
| `source` | text | app | `onboarding`. | onboarding |
| `language` | text | app | Language of `value`. | ta |

### `recurring_items`

The recurring payments behind the ledger: what a perfect recurring detector would find. (demo 75 rows · eval 1,860 rows; primary key: user_id, key)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `user_id` | text | app | Owner (`users.user_id`). | c282e400-dfa4-5c9d-9175-1f6089c85555 |
| `key` | text | app | Stable slug, unique per user. | recharge |
| `kind` | text | label | `subscription`, `bill`, `recharge`, `sip`, `insurance`, `fees`, `maid`, `emi`, `rent`, `remittance`, `lpg`, `ppf`, `milk`. | recharge |
| `name` | text | label | Readable name. | Mobile recharge |
| `category` | text | label | Category slug. | mobile_internet |
| `cadence` | text | label | `monthly`, `bimonthly`, `quarterly`, `yearly`, `every_28d` (prepaid packs) or `every_n_days` (gas refills). | every_28d |
| `day` | bigint | label | Usual day of the month it is paid (for yearly/quarterly, the day within the due month). Meaningless for `every_28d` / `every_n_days`: those repeat from `start_date`. | 1 |
| `channel` | text | label | How it is paid: `ach` (NACH auto-debit), `autopay` (UPI AutoPay), `card`, `upi_p2m`, `upi_p2p`, `netbanking`, `billpay` (bank BBPS), `neft`. | upi_p2m |
| `merchant_key` | text | label | Merchant slug (`synth_ref.merchants`). | jio |
| `payee` | text | label | Person paid, for P2P items (landlord, maid, tutor). | K NAGARAJ |
| `amount_paise` | bigint | label | Amount as of `data_end` (after any price hike). Typical amount for variable bills. | 34900 |
| `amount_is_variable` | boolean | label | True for bills that change every cycle (electricity, gas). A higher variable bill is not a price hike. | False |
| `account_role` | text | label | Which account pays (`accounts.role`). | primary |
| `start_date` | date | label | First payment on or after this date. | 2025-11-14 |
| `end_date` | date | label | Last payment (EMIs); empty = ongoing. | 2041-03-05 |
| `planted` | text | label | `price_hike` or `forgotten_subscription` if this item carries a planted pattern. | price_hike |

### `settlements`

Settle-up payments between members. (demo 56 rows · eval 420 rows; primary key: settlement_id)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `group_id` | text | app | Group (`groups.group_id`). | 49fac755-4f57-50c5-bbca-a58b1552e6b0 |
| `settlement_id` | text | app | UUID (stable: the same seed always gives the same id) | 111b7b87-5a3c-5d98-97d6-35c15b176831 |
| `from_member_id` | text | app | Who pays. | 50d982e8-1527-55fa-8248-c0856768df57 |
| `to_member_id` | text | app | Who receives. | dc75f547-51fd-5ee0-acc2-42f4a827edde |
| `amount_paise` | bigint | app | Amount in paise (₹1 = 100). Always positive. | 176800 |
| `status` | text | app | `pending`, `marked_paid` (payer says paid) or `confirmed` (receiver confirmed). | pending |
| `created_by_member_id` | text | app | Who created it. | dc75f547-51fd-5ee0-acc2-42f4a827edde |
| `created_at` | timestamptz | app | When it was created. | 2026-11-17T01:05:52+05:30 |
| `upi_link` | text | app | `upi://pay` deep link that opens any UPI app. | upi://pay?pa=arun.kumar@pocketdemo&pn=… |
| `marked_paid_at` | timestamptz | app | When marked paid. | 2026-11-17T05:20:52+05:30 |
| `confirmed_at` | timestamptz | app | When confirmed. | 2025-12-05T03:45:28+05:30 |

### `sms_messages`

Bank SMS for the demo personas (eval SMS are in `eval/sources/sms.jsonl.gz`). Demo only. (demo 7,443 rows · not in eval; primary key: sms_id)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `sms_id` | text | obs | Unique id (user prefix + sequence). It does not reveal the linked transaction. | c282e400-000001 |
| `user_id` | text | app | Owner (`users.user_id`). | c282e400-dfa4-5c9d-9175-1f6089c85555 |
| `sender_id` | text | obs | DLT sender header: 2-letter operator/circle code, the bank's 6-letter code, and `-S` (service), `-T` (transactional) or `-P` (promotional). | AX-KOTAKB |
| `body` | text | obs | Exact SMS text, including line breaks. | Received Rs.6000.00 in your Kotak Bank… |
| `received_at` | timestamptz | obs | When the phone received it (seconds to minutes after the transaction). | 2025-11-01T19:38:38+05:30 |
| `template_id` | text | label | `bank.template.version`. `.v3` wordings are held out. | kotak.upi_cr.v1 |
| `holdout` | boolean | label | True = a wording not used anywhere else. Measure parser accuracy on these only. | False |
| `transaction_id` | text | label | Transaction this SMS reports. Empty for OTPs, promos and statement notices. | 34268c2b-c27d-5775-ad7a-02fce3385948 |
| `ground_truth` | jsonb | label | JSON a perfect parser would output: `kind` (`debit`/`credit`/`ignore`), `amount_paise`, `account_last4`, `vpa`, `counterparty`, `ref_no`, `txn_date`, `balance_paise`, `mode`, `is_card`. `ignore` rows carry a `reason`. | {"kind": "credit", "amount_paise": 600… |

### `transactions`

Every posted debit and credit. Read in `occurred_at` order, `balance_after_paise` always chains. (demo 7,379 rows · eval 228,584 rows; primary key: txn_id)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `txn_id` | text | obs | UUID (stable: the same seed always gives the same id); doubles as the Account Aggregator `txnId`. | 34268c2b-c27d-5775-ad7a-02fce3385948 |
| `user_id` | text | app | Owner (`users.user_id`). | c282e400-dfa4-5c9d-9175-1f6089c85555 |
| `account_id` | text | app | Account (`accounts.account_id`). | 77fcc7ce-a3cf-5d4b-865b-5c6566bdb311 |
| `occurred_at` | timestamptz | obs | When it happened, ISO 8601 with +05:30. Postgres stores it in UTC; show it with `AT TIME ZONE 'Asia/Kolkata'`. | 2025-11-01T19:38:23+05:30 |
| `value_date` | date | obs | Value date (IST). | 2025-11-01 |
| `amount_paise` | bigint | obs | Amount in paise (₹1 = 100). Always positive; `direction` gives the sign. | 600000 |
| `direction` | text | obs | `debit` (money out of a bank account, or a new charge on a card) or `credit`. | credit |
| `mode` | text | obs | `upi`, `card`, `neft`, `imps`, `nach`, `atm`, `autopay` (UPI AutoPay mandate), `interest`, `cash`, `other`. | upi |
| `status` | text | label | `success`, or `reversed` for a failed UPI debit that came back. The feed shows both rows; the app must pair them. | success |
| `kind` | text | label | Fine type, e.g. `upi_p2m` (paid a merchant), `upi_p2p_out` (paid a person), `card_spend`, `ach_dr` (EMI/SIP auto-debit), `neft_in`, `imps_in`, `self_out`/`self_in` (own accounts), `card_bill_pay`/`card_payment_in`, `upi_reversal`, `card_refund`, `charge` (bank fee), `fin_charge`/`fin_charge_gst`, `fd_book`, `atm_wd`, `cash_dep`, `interest`. | upi_in |
| `merchant_key` | text | label | Resolved merchant. Empty for people, own transfers and bank entries. | uber |
| `counterparty_name` | text | obs | Name exactly as printed in the narration: legal names, typos and all (`ZOMTO`, `ETERNAL LIMITED`). | R RAMASAMY |
| `counterparty_vpa` | text | obs | Payee or payer UPI ID, when the bank shows one. | ramasamy.r@okaxis |
| `category_id` | text | label | True category. This is what the categoriser is scored against. | allowance |
| `narration` | text | obs | Statement narration in that bank's own style. | UPI/R RAMASAMY/530519071383/Pocket mon… |
| `ref_no` | text | obs | UPI RRN (12 digits: year digit + day of year + hour + 6 digits), NEFT UTR, or bank reference. | 530519071383 |
| `balance_after_paise` | bigint | obs | Balance right after this row. Cards: amount owed. | 920000 |
| `recurring_key` | text | label | Recurring item it belongs to (`recurring_items.key` for the same user). | allowance |
| `transfer_pair_id` | text | label | The other leg of an own-account transfer or card bill payment. | 64bff5fa-7c26-5982-9de7-772d615636f9 |
| `reversal_of_id` | text | label | For a `upi_reversal`: the failed debit it returns. | fcb5623c-deb0-5e42-8fbf-b7d9666d2bab |
| `refund_of_id` | text | label | For a refund: the purchase it refunds (may be partial). | f8cb13a4-0fd4-5979-b950-d8db56190332 |
| `group_expense_id` | text | app | Group expense this payment was entered as. | d30c8eb0-c47e-535b-aa06-0c981b709d7a |
| `group_id` | text | app | Group (`groups.group_id`). | 49fac755-4f57-50c5-bbca-a58b1552e6b0 |
| `settlement_id` | text | app | Settle-up this payment completes. | 14e15839-8516-5d10-88ef-e19b5ddb2aa6 |
| `sms_ids` | text | label | The SMS that reported this transaction (pipe-separated). What an SMS↔transaction matcher should output. | c282e400-000001 |
| `planted_pattern` | text | label | Set on the rows that make up a planted pattern. | price_hike |
| `source` | text | app | `aa` (from the Account Aggregator statement). | aa |

### `users`

One row per synthetic person. (demo 6 rows · eval 200 rows; primary key: user_id)

| Column | Type | Role | Meaning | Example |
| --- | --- | --- | --- | --- |
| `user_id` | text | app | Owner (`users.user_id`). | c282e400-dfa4-5c9d-9175-1f6089c85555 |
| `persona_id` | text | app | Demo persona: `student`, `first_job`, `family`, `gig`, `shop`, `investor`. Empty for eval users. | student |
| `archetype` | text | app | Life situation the person was generated from (same six values). | student |
| `display_name` | text | app | Full name (invented). | Karthik Ramasamy |
| `first_name` | text | app | First name. | Karthik |
| `gender` | text | app | `male` or `female`. | male |
| `age` | bigint | app | Age in years. | 20 |
| `city` | text | app | City (`synth_ref.cities`). | Chennai |
| `area` | text | app | Neighbourhood. | Velachery |
| `language` | text | app | Mascot language: `ta`, `hi` or `en`. | ta |
| `income_pattern` | text | app | `student`, `salaried`, `gig` or `business`. | student |
| `occupation` | text | app | Occupation. | B.Com second-year student |
| `household` | text | app | Who they live with. | Lives with parents and younger sister |
| `kind` | text | app | `demo` or `eval`. | demo |
| `planted_types` | text | label | Pattern types planted for this user (pipe-separated). Empty = nothing planted; the app should find nothing. | category_creep\|duplicate_charge\|expe… |
| `seed` | bigint | app | Random seed this person was generated from. | 1001 |
| `data_start` | date | app | First day of their history. | 2025-11-01 |
| `data_end` | date | app | Last day of their history. | 2026-11-19 |
