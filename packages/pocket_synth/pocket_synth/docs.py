"""Write DATA_DICTIONARY.md for a built pack: every table, every column, its SQL type, role and meaning.

    python -m pocket_synth.docs <pack-root>

Fails if any column in the CSVs has no description here, so the dictionary can't drift from the data.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

from .sqlgen import PK, infer, scan

# Role of each column:
#   obs   = a real bank feed (Account Aggregator JSON) or bank SMS gives you this. Parsers and detectors may read it.
#   label = ground truth. Never feed it to a parser, categoriser or detector you are evaluating.
#           (For the demo it is fine to load it as already-processed app state.)
#   app   = state the app or the user creates (budgets, goals, groups, ids).
#   ref   = reference data.
TABLES = {
    # ------------------------------------------------------------------ reference
    "banks": ("ref", "The 7 banks whose statement and SMS styles are modelled."),
    "categories": ("ref", "The fixed category slugs. `default_class` is the spend class before recurring detection."),
    "cities": ("ref", "The 15 cities personas live in, with local price anchors."),
    "festivals": ("ref", "Festival and sale windows that lift spending, with per-category multipliers."),
    "funds": ("ref", "16 real mutual fund schemes with their real latest NAV from AMFI."),
    "merchants": ("ref", "Merchants: real brands plus invented neighbourhood shops."),
    "nav_history_synthetic": ("ref", "Daily NAVs for the window. Only the last value per scheme is real (`source = amfi`)."),
    # ------------------------------------------------------------------ people and money
    "users": ("app", "One row per synthetic person."),
    "profile_facts": ("app", "What each demo persona told the mascot at onboarding, in their own language. Demo only."),
    "accounts": ("obs", "Bank accounts and credit cards."),
    "transactions": ("obs", "Every posted debit and credit. Read in `occurred_at` order, `balance_after_paise` always chains."),
    "sms_messages": ("obs", "Bank SMS for the demo personas (eval SMS are in `eval/sources/sms.jsonl.gz`). Demo only."),
    "balance_snapshots": ("obs", "End-of-day balance (IST) of every savings and current account, every day of the window."),
    "card_statements": ("obs", "Monthly credit card statements."),
    "recurring_items": ("label", "The recurring payments behind the ledger: what a perfect recurring detector would find."),
    "loans": ("obs", "Loans whose EMIs appear in the ledger."),
    "holdings": ("obs", "Mutual funds, fixed deposits, gold, PPF and EPF."),
    "planted_patterns": ("label", "The answer key: insights the app must find. One row per planted pattern."),
    # ------------------------------------------------------------------ app state
    "pockets": ("app", "Monthly budget envelopes the user set up."),
    "goals": ("app", "Savings goals."),
    "goal_contributions": ("app", "Money earmarked to goals, one row per month."),
    "groups": ("app", "Collab groups: trips, flatmates, families."),
    "group_members": ("app", "People in each group. Guests are not Pocket users."),
    "group_expenses": ("app", "Shared expenses entered in a group."),
    "group_expense_shares": ("app", "Who owes what for each expense. Shares always sum exactly to the expense."),
    "settlements": ("app", "Settle-up payments between members."),
    "group_pot_contributions": ("app", "Money members put into a group's shared pot (for a trip)."),
    "group_invites": ("app", "Invite codes for joining a group."),
}

ID = "UUID (stable: the same seed always gives the same id)"
COL = {
    # shared
    "user_id": ("app", "Owner (`users.user_id`)."),
    "account_id": ("app", "Account (`accounts.account_id`)."),
    "group_id": ("app", "Group (`groups.group_id`)."),
    "member_id": ("app", "Group member (`group_members.member_id`)."),
    "goal_id": ("app", "Goal (`goals.goal_id`)."),
    "expense_id": ("app", "Group expense (`group_expenses.expense_id`)."),
    "category_id": ("label", "Category slug (`synth_ref.categories`)."),
    "merchant_key": ("label", "Merchant slug (`synth_ref.merchants`)."),
    "emoji": ("app", "Display emoji."),
    "name": ("app", "Display name."),
    "status": ("app", "Lifecycle status."),
    "created_by": ("app", "Who created the row (`loader` = seeded with the data)."),
    "created_at": ("app", "When it was created."),
    "amount_paise": ("obs", "Amount in paise (₹1 = 100). Always positive."),
    "note": ("app", "Free-text note."),
    "key": ("app", "Stable slug, unique per user."),
    "kind": ("label", "Sub-type."),
    "description": ("app", "What the user typed."),
    "source": ("app", "Where the row came from."),
}
TCOL = {
    # reference
    ("banks", "bank_code"): ("ref", "Short code, e.g. `HDFC`, `SBI`."),
    ("banks", "name"): ("ref", "Bank name."),
    ("banks", "ifsc_prefix"): ("ref", "First 4 letters of every IFSC of this bank."),
    ("banks", "sms_sender_codes"): ("ref", "6-letter SMS sender codes used for account alerts (pipe-separated)."),
    ("banks", "card_sms_sender_codes"): ("ref", "Sender codes used for credit card alerts (pipe-separated)."),
    ("banks", "savings_rate_bps_approx"): ("ref", "Approximate savings interest rate, basis points (275 = 2.75% a year)."),
    ("banks", "account_number_length"): ("ref", "Digits in this bank's savings account numbers."),
    ("categories", "kind"): ("ref", "`income`, `refund`, `transfer`, `saving` or `expense`."),
    ("categories", "default_class"): ("ref", "Spend class before recurring detection: `income`, `refund`, `transfer`, `saving`, `committed`, `flexible`. A transaction linked to a recurring bill or subscription becomes `committed`."),
    ("categories", "name_en"): ("ref", "English label."),
    ("cities", "city"): ("ref", "City name."),
    ("cities", "state"): ("ref", "State."),
    ("cities", "region"): ("ref", "`south`, `north`, `west` or `east` (drives festivals and names)."),
    ("cities", "power_board"): ("ref", "Electricity board."),
    ("cities", "power_billing"): ("ref", "`monthly` or `bimonthly` billing."),
    ("cities", "petrol_per_litre_approx"): ("ref", "Approximate petrol price, ₹ per litre."),
    ("cities", "lpg_cylinder_approx"): ("ref", "Approximate 14.2 kg LPG cylinder price, ₹."),
    ("cities", "metro"): ("ref", "Whether the city has a metro rail system."),
    ("cities", "areas"): ("ref", "Neighbourhoods used for personas (pipe-separated)."),
    ("festivals", "name"): ("ref", "Festival or sale."),
    ("festivals", "start_date"): ("ref", "First day of the spending window."),
    ("festivals", "end_date"): ("ref", "Last day of the spending window."),
    ("festivals", "regions"): ("ref", "Regions it applies to (pipe-separated); `*` = everywhere."),
    ("festivals", "spend_multipliers"): ("ref", "JSON: category → spending multiplier during the window."),
    ("funds", "scheme_code"): ("ref", "AMFI scheme code."),
    ("funds", "scheme_name"): ("ref", "Scheme name as AMFI lists it."),
    ("funds", "category"): ("ref", "Fund category."),
    ("funds", "latest_nav"): ("ref", "Real NAV on `latest_nav_date`."),
    ("funds", "latest_nav_date"): ("ref", "Date of that NAV."),
    ("funds", "latest_nav_source"): ("ref", "Where the NAV was read."),
    ("merchants", "name"): ("ref", "Brand name shown in the app."),
    ("merchants", "narration_name"): ("ref", "Name as it usually appears in bank narrations (often the legal entity, e.g. `BUNDL TECHNOLOGIES` for Swiggy)."),
    ("merchants", "subcategory"): ("ref", "Finer label."),
    ("merchants", "vpa_pattern"): ("ref", "UPI ID the merchant collects on; `{n}` is replaced by digits per store."),
    ("merchants", "cities"): ("ref", "Cities where it operates (pipe-separated); `*` = everywhere."),
    ("merchants", "is_subscription_likely"): ("ref", "True for services usually paid monthly."),
    ("merchants", "is_local"): ("ref", "True for invented neighbourhood shops (tea stalls, kirana, medical stores)."),
    ("merchants", "aliases"): ("ref", "Other spellings seen in narrations, including typos (pipe-separated)."),
    ("nav_history_synthetic", "scheme_code"): ("ref", "AMFI scheme code (`synth_ref.funds`)."),
    ("nav_history_synthetic", "nav_date"): ("ref", "Date."),
    ("nav_history_synthetic", "nav"): ("ref", "NAV on that date."),
    ("nav_history_synthetic", "source"): ("ref", "`amfi` (real, last day only) or `synthetic_backfill`."),
    # users
    ("users", "persona_id"): ("app", "Demo persona: `student`, `first_job`, `family`, `gig`, `shop`, `investor`. Empty for eval users."),
    ("users", "archetype"): ("app", "Life situation the person was generated from (same six values)."),
    ("users", "display_name"): ("app", "Full name (invented)."),
    ("users", "first_name"): ("app", "First name."),
    ("users", "gender"): ("app", "`male` or `female`."),
    ("users", "age"): ("app", "Age in years."),
    ("users", "city"): ("app", "City (`synth_ref.cities`)."),
    ("users", "area"): ("app", "Neighbourhood."),
    ("users", "language"): ("app", "Mascot language: `ta`, `hi` or `en`."),
    ("users", "income_pattern"): ("app", "`student`, `salaried`, `gig` or `business`."),
    ("users", "occupation"): ("app", "Occupation."),
    ("users", "household"): ("app", "Who they live with."),
    ("users", "kind"): ("app", "`demo` or `eval`."),
    ("users", "planted_types"): ("label", "Pattern types planted for this user (pipe-separated). Empty = nothing planted; the app should find nothing."),
    ("users", "seed"): ("app", "Random seed this person was generated from."),
    ("users", "data_start"): ("app", "First day of their history."),
    ("users", "data_end"): ("app", "Last day of their history."),
    # profile facts
    ("profile_facts", "key"): ("app", "`occupation`, `income`, `saving_for`, `worries` or `household`."),
    ("profile_facts", "value"): ("app", "What they said, in their language."),
    ("profile_facts", "source"): ("app", "`onboarding`."),
    ("profile_facts", "language"): ("app", "Language of `value`."),
    # accounts
    ("accounts", "account_id"): ("app", ID),
    ("accounts", "role"): ("label", "Generator's role for the account: `primary`, `secondary`, `card`, `business`. Not something a bank reports."),
    ("accounts", "provider"): ("app", "`synthetic` (in production: the Account Aggregator data provider)."),
    ("accounts", "institution_code"): ("obs", "Bank code (`synth_ref.banks`)."),
    ("accounts", "institution_name"): ("obs", "Bank name."),
    ("accounts", "type"): ("obs", "`savings`, `current` or `credit_card`."),
    ("accounts", "masked_number"): ("obs", "Masked number as banks show it; length follows the bank's real account-number length (cards: 16)."),
    ("accounts", "ifsc"): ("obs", "Branch IFSC (4-letter bank code + `0` + 6 characters). Empty for cards."),
    ("accounts", "nickname"): ("app", "User's name for the account."),
    ("accounts", "opened_on"): ("obs", "Account opening date."),
    ("accounts", "opening_balance_paise"): ("obs", "Balance at the start of `data_start`, before the first transaction. Cards: amount owed."),
    ("accounts", "current_balance_paise"): ("obs", "Balance at 23:59:59 IST on `data_end`. Cards: amount owed."),
    ("accounts", "balance_as_of"): ("obs", "Time of `current_balance_paise`."),
    ("accounts", "credit_limit_paise"): ("obs", "Card limit. Empty for bank accounts."),
    ("accounts", "interest_rate_bps"): ("obs", "Yearly rate in basis points. Savings: interest earned (275 = 2.75%). Cards: finance charge (4320 = 43.2% a year, 3.6% a month)."),
    ("accounts", "statement_day"): ("obs", "Card statement day of month."),
    ("accounts", "due_day"): ("obs", "Card payment due day of month (about 20 days after the statement)."),
    # transactions
    ("transactions", "txn_id"): ("obs", ID + "; doubles as the Account Aggregator `txnId`."),
    ("transactions", "amount_paise"): ("obs", "Amount in paise (₹1 = 100). Always positive; `direction` gives the sign."),
    ("transactions", "occurred_at"): ("obs", "When it happened, ISO 8601 with +05:30. Postgres stores it in UTC; show it with `AT TIME ZONE 'Asia/Kolkata'`."),
    ("transactions", "value_date"): ("obs", "Value date (IST)."),
    ("transactions", "direction"): ("obs", "`debit` (money out of a bank account, or a new charge on a card) or `credit`."),
    ("transactions", "mode"): ("obs", "`upi`, `card`, `neft`, `imps`, `nach`, `atm`, `autopay` (UPI AutoPay mandate), `interest`, `cash`, `other`."),
    ("transactions", "status"): ("label", "`success`, or `reversed` for a failed UPI debit that came back. The feed shows both rows; the app must pair them."),
    ("transactions", "kind"): ("label", "Fine type, e.g. `upi_p2m` (paid a merchant), `upi_p2p_out` (paid a person), `card_spend`, `ach_dr` (EMI/SIP auto-debit), `neft_in`, `imps_in`, `self_out`/`self_in` (own accounts), `card_bill_pay`/`card_payment_in`, `upi_reversal`, `card_refund`, `charge` (bank fee), `fin_charge`/`fin_charge_gst`, `fd_book`, `atm_wd`, `cash_dep`, `interest`."),
    ("transactions", "merchant_key"): ("label", "Resolved merchant. Empty for people, own transfers and bank entries."),
    ("transactions", "counterparty_name"): ("obs", "Name exactly as printed in the narration: legal names, typos and all (`ZOMTO`, `ETERNAL LIMITED`)."),
    ("transactions", "counterparty_vpa"): ("obs", "Payee or payer UPI ID, when the bank shows one."),
    ("transactions", "category_id"): ("label", "True category. This is what the categoriser is scored against."),
    ("transactions", "narration"): ("obs", "Statement narration in that bank's own style."),
    ("transactions", "ref_no"): ("obs", "UPI RRN (12 digits: year digit + day of year + hour + 6 digits), NEFT UTR, or bank reference."),
    ("transactions", "balance_after_paise"): ("obs", "Balance right after this row. Cards: amount owed."),
    ("transactions", "recurring_key"): ("label", "Recurring item it belongs to (`recurring_items.key` for the same user)."),
    ("transactions", "transfer_pair_id"): ("label", "The other leg of an own-account transfer or card bill payment."),
    ("transactions", "reversal_of_id"): ("label", "For a `upi_reversal`: the failed debit it returns."),
    ("transactions", "refund_of_id"): ("label", "For a refund: the purchase it refunds (may be partial)."),
    ("transactions", "group_expense_id"): ("app", "Group expense this payment was entered as."),
    ("transactions", "settlement_id"): ("app", "Settle-up this payment completes."),
    ("transactions", "sms_ids"): ("label", "The SMS that reported this transaction (pipe-separated). What an SMS↔transaction matcher should output."),
    ("transactions", "planted_pattern"): ("label", "Set on the rows that make up a planted pattern."),
    ("transactions", "source"): ("app", "`aa` (from the Account Aggregator statement)."),
    # sms
    ("sms_messages", "sms_id"): ("obs", "Unique id (user prefix + sequence). It does not reveal the linked transaction."),
    ("sms_messages", "sender_id"): ("obs", "DLT sender header: 2-letter operator/circle code, the bank's 6-letter code, and `-S` (service), `-T` (transactional) or `-P` (promotional)."),
    ("sms_messages", "body"): ("obs", "Exact SMS text, including line breaks."),
    ("sms_messages", "received_at"): ("obs", "When the phone received it (seconds to minutes after the transaction)."),
    ("sms_messages", "template_id"): ("label", "`bank.template.version`. `.v3` wordings are held out."),
    ("sms_messages", "holdout"): ("label", "True = a wording not used anywhere else. Measure parser accuracy on these only."),
    ("sms_messages", "transaction_id"): ("label", "Transaction this SMS reports. Empty for OTPs, promos and statement notices."),
    ("sms_messages", "ground_truth"): ("label", "JSON a perfect parser would output: `kind` (`debit`/`credit`/`ignore`), `amount_paise`, `account_last4`, `vpa`, `counterparty`, `ref_no`, `txn_date`, `balance_paise`, `mode`, `is_card`. `ignore` rows carry a `reason`."),
    # snapshots / statements
    ("balance_snapshots", "as_of_date"): ("obs", "Day (IST)."),
    ("balance_snapshots", "balance_paise"): ("obs", "Balance at the end of that day."),
    ("card_statements", "statement_date"): ("obs", "Statement date."),
    ("card_statements", "due_date"): ("obs", "Payment due date (20 days later)."),
    ("card_statements", "total_due_paise"): ("obs", "Total amount due."),
    ("card_statements", "min_due_paise"): ("obs", "Minimum due: 5% of the total, at least ₹200 (the whole total if smaller)."),
    ("card_statements", "paid_paise"): ("obs", "Paid before the due date. Empty = due date is after `data_end`."),
    ("card_statements", "finance_charges_paise"): ("obs", "Finance charges plus 18% GST billed on this statement."),
    ("card_statements", "revolving_after_due_paise"): ("obs", "Unpaid amount carried past the due date. Empty = paid in full."),
    ("card_statements", "finance_charges_next_paise"): ("obs", "Charges (with GST) that this statement's unpaid amount caused; billed on the next statement."),
    # recurring
    ("recurring_items", "kind"): ("label", "`subscription`, `bill`, `recharge`, `sip`, `insurance`, `fees`, `maid`, `emi`, `rent`, `remittance`, `lpg`, `ppf`, `milk`."),
    ("recurring_items", "name"): ("label", "Readable name."),
    ("recurring_items", "category"): ("label", "Category slug."),
    ("recurring_items", "cadence"): ("label", "`monthly`, `bimonthly`, `quarterly`, `yearly`, `every_28d` (prepaid packs) or `every_n_days` (gas refills)."),
    ("recurring_items", "day"): ("label", "Usual day of the month it is paid (for yearly/quarterly, the day within the due month). Meaningless for `every_28d` / `every_n_days`: those repeat from `start_date`."),
    ("recurring_items", "channel"): ("label", "How it is paid: `ach` (NACH auto-debit), `autopay` (UPI AutoPay), `card`, `upi_p2m`, `upi_p2p`, `netbanking`, `billpay` (bank BBPS), `neft`."),
    ("recurring_items", "payee"): ("label", "Person paid, for P2P items (landlord, maid, tutor)."),
    ("recurring_items", "amount_paise"): ("label", "Amount as of `data_end` (after any price hike). Typical amount for variable bills."),
    ("recurring_items", "amount_is_variable"): ("label", "True for bills that change every cycle (electricity, gas). A higher variable bill is not a price hike."),
    ("recurring_items", "account_role"): ("label", "Which account pays (`accounts.role`)."),
    ("recurring_items", "start_date"): ("label", "First payment on or after this date."),
    ("recurring_items", "end_date"): ("label", "Last payment (EMIs); empty = ongoing."),
    ("recurring_items", "planted"): ("label", "`price_hike` or `forgotten_subscription` if this item carries a planted pattern."),
    # loans
    ("loans", "lender"): ("obs", "Lender."),
    ("loans", "loan_type"): ("obs", "`home`, `vehicle`, `consumer_durable`, `business`."),
    ("loans", "rate_type"): ("obs", "`fixed` or `floating`."),
    ("loans", "principal_paise"): ("obs", "Amount borrowed."),
    ("loans", "outstanding_paise"): ("obs", "Principal still owed at `data_end`."),
    ("loans", "interest_rate_bps"): ("obs", "Yearly rate in basis points (815 = 8.15%)."),
    ("loans", "tenure_months"): ("obs", "Total EMIs."),
    ("loans", "emi_paise"): ("obs", "Monthly EMI."),
    ("loans", "emi_day"): ("obs", "Day of month the EMI is debited."),
    ("loans", "start_date"): ("obs", "First EMI date (can be before the window)."),
    ("loans", "end_date"): ("obs", "Last EMI date."),
    ("loans", "emis_paid"): ("obs", "EMIs paid up to `data_end`, including those before the window."),
    ("loans", "months_left"): ("obs", "EMIs still to pay."),
    ("loans", "zero_cost_emi"): ("obs", "True = no-cost EMI (0% interest, principal split evenly)."),
    # holdings
    ("holdings", "kind"): ("obs", "`mutual_fund`, `fd`, `gold`, `ppf` or `epf`."),
    ("holdings", "name"): ("obs", "Scheme, deposit or account name."),
    ("holdings", "scheme_code"): ("obs", "AMFI code (`synth_ref.funds`). Mutual funds only."),
    ("holdings", "units"): ("obs", "Units held at `data_end`."),
    ("holdings", "invested_paise"): ("obs", "Total invested."),
    ("holdings", "sip_amount_paise"): ("obs", "Monthly SIP."),
    ("holdings", "sip_day"): ("obs", "SIP debit day."),
    ("holdings", "folio_masked"): ("obs", "Masked folio number."),
    ("holdings", "platform"): ("obs", "Order platform (`BSE StAR MF`, `NSE NMF II`)."),
    ("holdings", "fd_principal_paise"): ("obs", "FD amount."),
    ("holdings", "fd_rate_bps"): ("obs", "FD rate, basis points a year."),
    ("holdings", "fd_start_date"): ("obs", "FD booking date."),
    ("holdings", "fd_maturity_date"): ("obs", "FD maturity date."),
    ("holdings", "gold_grams"): ("obs", "Grams of gold. No gold price is included."),
    ("holdings", "balance_paise"): ("obs", "PPF/EPF balance."),
    ("holdings", "balance_as_of"): ("obs", "Date of that balance (31 March statement)."),
    ("holdings", "booked_by"): ("obs", "`sweep` = the bank's auto-sweep moved surplus into an FD; `user` = booked by hand."),
    ("holdings", "latest_nav"): ("obs", "Real latest NAV."),
    ("holdings", "latest_nav_date"): ("obs", "Its date."),
    ("holdings", "value_at_latest_nav_paise"): ("obs", "`units × latest_nav`, in paise."),
    # pockets / goals
    ("pockets", "pocket_id"): ("app", ID),
    ("pockets", "monthly_limit_paise"): ("app", "Monthly budget."),
    ("pockets", "category_ids"): ("app", "Categories this pocket covers (pipe-separated)."),
    ("pockets", "sort_order"): ("app", "Display order."),
    ("goals", "target_paise"): ("app", "Target amount."),
    ("goals", "deadline"): ("app", "Target date; empty = none."),
    ("goals", "monthly_plan_paise"): ("app", "Planned monthly saving; empty = none."),
    ("goals", "priority"): ("app", "1 = the user's main goal."),
    ("goals", "saved_paise"): ("app", "Sum of `goal_contributions` up to `data_end`."),
    ("goal_contributions", "month"): ("app", "Month (first day)."),
    ("goal_contributions", "source"): ("app", "`loader`."),
    ("goal_contributions", "note"): ("app", "`Already saved at setup` or `Monthly`."),
    # groups
    ("groups", "key"): ("app", "Template key, e.g. `demo_student`."),
    ("groups", "type"): ("app", "`trip`, `flatmates` or `family`."),
    ("groups", "owner_user_id"): ("app", "Creator (`users.user_id`)."),
    ("groups", "budget_monthly_paise"): ("app", "Shared monthly budget; empty = none."),
    ("groups", "pot_target_paise"): ("app", "Shared pot target (trips)."),
    ("groups", "pot_deadline"): ("app", "Pot deadline."),
    ("group_members", "member_id"): ("app", ID),
    ("group_members", "user_id"): ("app", "Pocket user, if the member is one; empty for guests."),
    ("group_members", "display_name"): ("app", "Name shown in the group (invented)."),
    ("group_members", "vpa"): ("app", "UPI ID for settle-up links. Always `@pocketdemo`, a handle no bank routes."),
    ("group_members", "role"): ("app", "`owner` or `guest`."),
    ("group_members", "join_order"): ("app", "0 = owner. In equal splits the leftover paise go to the lowest `join_order` first."),
    ("group_members", "sharing"): ("app", "JSON: what this member shares with the group (`category_ids`, `show_transactions`, `goal_ids`)."),
    ("group_expenses", "paid_by_member_id"): ("app", "Who paid."),
    ("group_expenses", "occurred_at"): ("app", "When."),
    ("group_expenses", "split_method"): ("app", "`equal`, `percent` or `exact`."),
    ("group_expenses", "split_input"): ("app", "JSON the user entered: `{member_ids}` (equal), `{percent: {member: pct}}`, or `{paise: {member: paise}}` (exact)."),
    ("group_expenses", "linked_transaction_id"): ("app", "The payer's bank or card transaction, when the payer is a synthetic user."),
    ("group_expenses", "created_by_member_id"): ("app", "Who entered it."),
    ("group_expenses", "is_deleted"): ("app", "Soft delete flag."),
    ("group_expense_shares", "share_paise"): ("app", "This member's share."),
    ("settlements", "settlement_id"): ("app", ID),
    ("settlements", "from_member_id"): ("app", "Who pays."),
    ("settlements", "to_member_id"): ("app", "Who receives."),
    ("settlements", "status"): ("app", "`pending`, `marked_paid` (payer says paid) or `confirmed` (receiver confirmed)."),
    ("settlements", "created_by_member_id"): ("app", "Who created it."),
    ("settlements", "upi_link"): ("app", "`upi://pay` deep link that opens any UPI app."),
    ("settlements", "marked_paid_at"): ("app", "When marked paid."),
    ("settlements", "confirmed_at"): ("app", "When confirmed."),
    ("group_pot_contributions", "id"): ("app", ID),
    ("group_pot_contributions", "method"): ("app", "`upi`."),
    ("group_pot_contributions", "occurred_at"): ("app", "When."),
    ("group_invites", "created_by"): ("app", "`users.user_id` of the creator."),
    ("group_invites", "max_uses"): ("app", "How many people can join with it."),
    ("group_invites", "code"): ("app", "6-character invite code."),
    ("group_invites", "expires_at"): ("app", "Expiry date."),
    ("group_invites", "uses"): ("app", "Times used."),
    # planted patterns (sparse: each pattern type fills its own columns)
    ("planted_patterns", "pattern_type"): ("label", "`forgotten_subscription`, `price_hike`, `category_creep`, `duplicate_charge`, `idle_cash`, `expensive_card_balance`."),
    ("planted_patterns", "natural_key"): ("label", "Stable key a detector's output can be matched on (format per type in the README)."),
    ("planted_patterns", "merchant_key"): ("label", "Merchant involved (subscription, price hike, duplicate)."),
    ("planted_patterns", "mandate_txn_id"): ("label", "Forgotten subscription: the ₹1–₹2 mandate check debit at sign-up."),
    ("planted_patterns", "mandate_date"): ("label", "Forgotten subscription: sign-up date."),
    ("planted_patterns", "mandate_amount_paise"): ("label", "Forgotten subscription: mandate check amount."),
    ("planted_patterns", "first_charge_date"): ("label", "Forgotten subscription: first full charge after the free trial."),
    ("planted_patterns", "monthly_amount_paise"): ("label", "Forgotten subscription: monthly charge."),
    ("planted_patterns", "charges"): ("label", "Forgotten subscription: full charges so far."),
    ("planted_patterns", "total_paid_paise"): ("label", "Forgotten subscription: total paid so far."),
    ("planted_patterns", "account_id"): ("label", "Account involved."),
    ("planted_patterns", "recurring_key"): ("label", "Recurring item involved."),
    ("planted_patterns", "old_amount_paise"): ("label", "Price hike: old price."),
    ("planted_patterns", "new_amount_paise"): ("label", "Price hike: new price."),
    ("planted_patterns", "first_new_charge_date"): ("label", "Price hike: first charge at the new price."),
    ("planted_patterns", "latest_txn_id"): ("label", "Price hike: latest charge."),
    ("planted_patterns", "increase_pct"): ("label", "Price hike or creep: rise in whole percent."),
    ("planted_patterns", "category_id"): ("label", "Creep: category (`food_delivery`)."),
    ("planted_patterns", "earlier_months"): ("label", "Creep: the 3 baseline months (comma-separated `YYYY-MM`)."),
    ("planted_patterns", "recent_months"): ("label", "Creep: the 3 recent months."),
    ("planted_patterns", "earlier_avg_paise"): ("label", "Creep: monthly average in the baseline months."),
    ("planted_patterns", "recent_avg_paise"): ("label", "Creep: monthly average in the recent months."),
    ("planted_patterns", "this_month_to_date_paise"): ("label", "Creep: spend so far in the current month."),
    ("planted_patterns", "first_txn_id"): ("label", "Duplicate: the genuine charge."),
    ("planted_patterns", "second_txn_id"): ("label", "Duplicate: the repeat charge."),
    ("planted_patterns", "amount_paise"): ("label", "Duplicate: amount charged twice."),
    ("planted_patterns", "first_at"): ("label", "Duplicate: time of the first charge."),
    ("planted_patterns", "second_at"): ("label", "Duplicate: time of the second (within 10 minutes)."),
    ("planted_patterns", "both_posted"): ("label", "Duplicate: both charges are in the ledger."),
    ("planted_patterns", "account_masked"): ("label", "Idle cash: masked account number."),
    ("planted_patterns", "bank"): ("label", "Bank code."),
    ("planted_patterns", "min_balance_60d_paise"): ("label", "Idle cash: lowest end-of-day balance in the last 60 days."),
    ("planted_patterns", "avg_monthly_outflow_paise"): ("label", "Idle cash: this account's average monthly outflow over the last 3 complete months."),
    ("planted_patterns", "buffer_paise"): ("label", "Idle cash: 1.5 × that outflow, kept as a safety buffer."),
    ("planted_patterns", "idle_paise"): ("label", "Idle cash: minimum balance − buffer, rounded down to ₹1,000."),
    ("planted_patterns", "threshold_paise"): ("label", "Idle cash: flag only if idle ≥ max(₹25,000, 0.5 × outflow)."),
    ("planted_patterns", "flagged"): ("label", "Idle cash: passed the threshold."),
    ("planted_patterns", "definition"): ("label", "Idle cash: the rule in words."),
    ("planted_patterns", "card_masked"): ("label", "Card balance: masked card number."),
    ("planted_patterns", "monthly_rate_bps"): ("label", "Card balance: monthly finance-charge rate (360 = 3.6%)."),
    ("planted_patterns", "finance_charge_txn_ids"): ("label", "Card balance: finance charge and GST rows (comma-separated)."),
    ("planted_patterns", "finance_charges_paise"): ("label", "Card balance: total finance charges + GST paid."),
    ("planted_patterns", "last_charge_date"): ("label", "Card balance: latest finance charge."),
    ("planted_patterns", "outstanding_at_end_paise"): ("label", "Card balance: amount owed at `data_end`."),
    ("planted_patterns", "revolving_statements"): ("label", "Card balance: statements not paid in full (comma-separated `YYYY-MM`)."),
}


def describe(table: str, col: str):
    if (table, col) in TCOL:
        return TCOL[(table, col)]
    if col in COL:
        role, d = COL[col]
        if TABLES[table][0] == "app":   # e.g. a group expense's amount or category is what the user entered
            role = "app"
        return role, d
    raise KeyError(f"no description for {table}.{col}")


def esc(v: str, n: int = 38) -> str:
    v = v.replace("\n", " ⏎ ").replace("|", "\\|")
    return (v[:n] + "…") if len(v) > n else v


def main(root: Path):
    out = ["# Data dictionary", "",
           "Generated from the CSVs by `python -m pocket_synth.docs`; every column is listed. Types are what `load_*.sql` creates.", "",
           "**Role** column: `obs` = a real bank feed or SMS gives you this, so parsers and detectors may read it; "
           "`label` = ground truth, never shown to what you are evaluating; `app` = state the app or user creates; `ref` = reference data.", "",
           "Lists inside a cell are `|`-separated unless the column says comma-separated. Empty cell = NULL.", ""]
    groups = [("Reference (`reference/`, schema `synth_ref`)", "reference", None),
              ("Demo and eval (`demo/db/` → `synth_demo`, `eval/db/` → `synth_eval`)", "demo/db", "eval/db")]
    for title, folder, other in groups:
        out += [f"## {title}", ""]
        for p in sorted((root / folder).glob("*.csv")):
            t = p.stem
            header, cols, n = scan(p)
            n_eval = None
            if other and (root / other / p.name).exists():
                with open(root / other / p.name, encoding="utf-8", newline="") as f:
                    n_eval = sum(1 for _ in csv.reader(f)) - 1
            role, tdesc = TABLES[t]
            counts = f"{n:,} rows" if not other else f"demo {n:,} rows · eval {n_eval:,} rows" if n_eval is not None else f"demo {n:,} rows · not in eval"
            pk = ", ".join(PK.get(t, [])) or "none"
            out += [f"### `{t}`", "", f"{tdesc} ({counts}; primary key: {pk})", "",
                    "| Column | Type | Role | Meaning | Example |", "| --- | --- | --- | --- | --- |"]
            for c, vals in zip(header, cols):
                r, d = describe(t, c)
                ex = next((v for v in vals if v != ""), "")
                out.append(f"| `{c}` | {infer(c, vals)} | {r} | {d} | {esc(ex)} |")
            out.append("")
    (root / "DATA_DICTIONARY.md").write_text("\n".join(out), encoding="utf-8")
    print("wrote", root / "DATA_DICTIONARY.md")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
