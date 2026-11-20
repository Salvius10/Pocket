-- Pocket synthetic data: the 200 evaluation users (answer key in synth_eval.planted_patterns)
-- Run from the pack's root folder (the one holding README.md):
--   psql "$DATABASE_URL" -f load_eval.sql
-- Safe to re-run: each table is dropped and reloaded. Money is integer paise; times carry +05:30 (IST).
\set ON_ERROR_STOP on
\encoding UTF8
SET client_min_messages = warning;
BEGIN;

CREATE SCHEMA IF NOT EXISTS synth_eval;
DROP TABLE IF EXISTS synth_eval.accounts;
CREATE TABLE synth_eval.accounts (
  "account_id" text,
  "user_id" text,
  "role" text,
  "provider" text,
  "institution_code" text,
  "institution_name" text,
  "type" text,
  "masked_number" text,
  "ifsc" text,
  "nickname" text,
  "opened_on" date,
  "opening_balance_paise" bigint,
  "current_balance_paise" bigint,
  "balance_as_of" timestamptz,
  "credit_limit_paise" bigint,
  "interest_rate_bps" bigint,
  "statement_day" bigint,
  "due_day" bigint,
  PRIMARY KEY ("account_id")
);
\copy synth_eval.accounts FROM 'eval/db/accounts.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_eval.balance_snapshots;
CREATE TABLE synth_eval.balance_snapshots (
  "account_id" text,
  "as_of_date" date,
  "balance_paise" bigint,
  PRIMARY KEY ("account_id", "as_of_date")
);
\copy synth_eval.balance_snapshots FROM 'eval/db/balance_snapshots.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_eval.card_statements;
CREATE TABLE synth_eval.card_statements (
  "account_id" text,
  "user_id" text,
  "statement_date" date,
  "due_date" date,
  "total_due_paise" bigint,
  "min_due_paise" bigint,
  "paid_paise" bigint,
  "finance_charges_paise" bigint,
  "revolving_after_due_paise" bigint,
  "finance_charges_next_paise" bigint,
  PRIMARY KEY ("account_id", "statement_date")
);
\copy synth_eval.card_statements FROM 'eval/db/card_statements.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_eval.goal_contributions;
CREATE TABLE synth_eval.goal_contributions (
  "goal_id" text,
  "user_id" text,
  "amount_paise" bigint,
  "month" date,
  "source" text,
  "note" text
);
\copy synth_eval.goal_contributions FROM 'eval/db/goal_contributions.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_eval.goals;
CREATE TABLE synth_eval.goals (
  "goal_id" text,
  "user_id" text,
  "name" text,
  "emoji" text,
  "target_paise" bigint,
  "deadline" text,
  "monthly_plan_paise" bigint,
  "priority" bigint,
  "status" text,
  "created_by" text,
  "created_at" date,
  "saved_paise" bigint,
  PRIMARY KEY ("goal_id")
);
\copy synth_eval.goals FROM 'eval/db/goals.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_eval.group_expense_shares;
CREATE TABLE synth_eval.group_expense_shares (
  "expense_id" text,
  "member_id" text,
  "share_paise" bigint,
  PRIMARY KEY ("expense_id", "member_id")
);
\copy synth_eval.group_expense_shares FROM 'eval/db/group_expense_shares.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_eval.group_expenses;
CREATE TABLE synth_eval.group_expenses (
  "expense_id" text,
  "group_id" text,
  "paid_by_member_id" text,
  "amount_paise" bigint,
  "description" text,
  "category_id" text,
  "occurred_at" timestamptz,
  "split_method" text,
  "split_input" jsonb,
  "linked_transaction_id" text,
  "created_by_member_id" text,
  "is_deleted" boolean,
  PRIMARY KEY ("expense_id")
);
\copy synth_eval.group_expenses FROM 'eval/db/group_expenses.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_eval.group_invites;
CREATE TABLE synth_eval.group_invites (
  "group_id" text,
  "created_by" text,
  "max_uses" bigint,
  "code" text,
  "expires_at" date,
  "uses" bigint,
  PRIMARY KEY ("code")
);
\copy synth_eval.group_invites FROM 'eval/db/group_invites.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_eval.group_members;
CREATE TABLE synth_eval.group_members (
  "member_id" text,
  "group_id" text,
  "user_id" text,
  "display_name" text,
  "vpa" text,
  "role" text,
  "join_order" bigint,
  "sharing" jsonb,
  PRIMARY KEY ("member_id")
);
\copy synth_eval.group_members FROM 'eval/db/group_members.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_eval.groups;
CREATE TABLE synth_eval.groups (
  "group_id" text,
  "key" text,
  "type" text,
  "name" text,
  "emoji" text,
  "owner_user_id" text,
  "created_at" date,
  "budget_monthly_paise" bigint,
  "pot_target_paise" bigint,
  "pot_deadline" text,
  "status" text,
  PRIMARY KEY ("group_id")
);
\copy synth_eval.groups FROM 'eval/db/groups.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_eval.holdings;
CREATE TABLE synth_eval.holdings (
  "user_id" text,
  "kind" text,
  "name" text,
  "scheme_code" integer,
  "units" numeric,
  "invested_paise" bigint,
  "sip_amount_paise" bigint,
  "sip_day" bigint,
  "folio_masked" text,
  "platform" text,
  "fd_principal_paise" bigint,
  "fd_rate_bps" bigint,
  "fd_start_date" date,
  "fd_maturity_date" date,
  "gold_grams" text,
  "balance_paise" text,
  "balance_as_of" text,
  "booked_by" text,
  "latest_nav" numeric,
  "latest_nav_date" date,
  "value_at_latest_nav_paise" bigint
);
\copy synth_eval.holdings FROM 'eval/db/holdings.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_eval.loans;
CREATE TABLE synth_eval.loans (
  "user_id" text,
  "key" text,
  "lender" text,
  "loan_type" text,
  "rate_type" text,
  "principal_paise" bigint,
  "outstanding_paise" bigint,
  "interest_rate_bps" bigint,
  "tenure_months" bigint,
  "emi_paise" bigint,
  "emi_day" bigint,
  "start_date" date,
  "end_date" date,
  "emis_paid" bigint,
  "months_left" bigint,
  "zero_cost_emi" boolean,
  PRIMARY KEY ("user_id", "key")
);
\copy synth_eval.loans FROM 'eval/db/loans.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_eval.planted_patterns;
CREATE TABLE synth_eval.planted_patterns (
  "user_id" text,
  "pattern_type" text,
  "natural_key" text,
  "account_id" text,
  "account_masked" text,
  "bank" text,
  "min_balance_60d_paise" bigint,
  "avg_monthly_outflow_paise" bigint,
  "buffer_paise" bigint,
  "idle_paise" bigint,
  "threshold_paise" bigint,
  "flagged" boolean,
  "definition" text,
  "merchant_key" text,
  "first_txn_id" text,
  "second_txn_id" text,
  "amount_paise" bigint,
  "first_at" timestamptz,
  "second_at" timestamptz,
  "both_posted" boolean,
  "mandate_txn_id" text,
  "mandate_date" date,
  "mandate_amount_paise" bigint,
  "first_charge_date" date,
  "monthly_amount_paise" bigint,
  "charges" bigint,
  "total_paid_paise" bigint,
  "recurring_key" text,
  "old_amount_paise" bigint,
  "new_amount_paise" bigint,
  "first_new_charge_date" date,
  "latest_txn_id" text,
  "increase_pct" bigint,
  "category_id" text,
  "earlier_months" text,
  "recent_months" text,
  "earlier_avg_paise" bigint,
  "recent_avg_paise" bigint,
  "this_month_to_date_paise" bigint,
  "card_masked" text,
  "monthly_rate_bps" bigint,
  "finance_charge_txn_ids" text,
  "finance_charges_paise" bigint,
  "last_charge_date" date,
  "outstanding_at_end_paise" bigint,
  "revolving_statements" text,
  PRIMARY KEY ("user_id", "natural_key")
);
\copy synth_eval.planted_patterns FROM 'eval/db/planted_patterns.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_eval.pockets;
CREATE TABLE synth_eval.pockets (
  "pocket_id" text,
  "user_id" text,
  "name" text,
  "emoji" text,
  "monthly_limit_paise" bigint,
  "category_ids" text,
  "status" text,
  "sort_order" bigint,
  "created_by" text,
  "created_at" date,
  PRIMARY KEY ("pocket_id")
);
\copy synth_eval.pockets FROM 'eval/db/pockets.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_eval.recurring_items;
CREATE TABLE synth_eval.recurring_items (
  "user_id" text,
  "key" text,
  "kind" text,
  "name" text,
  "category" text,
  "cadence" text,
  "day" bigint,
  "channel" text,
  "merchant_key" text,
  "payee" text,
  "amount_paise" bigint,
  "amount_is_variable" boolean,
  "account_role" text,
  "start_date" date,
  "end_date" date,
  "planted" text,
  PRIMARY KEY ("user_id", "key")
);
\copy synth_eval.recurring_items FROM 'eval/db/recurring_items.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_eval.settlements;
CREATE TABLE synth_eval.settlements (
  "group_id" text,
  "settlement_id" text,
  "from_member_id" text,
  "to_member_id" text,
  "amount_paise" bigint,
  "status" text,
  "created_by_member_id" text,
  "created_at" timestamptz,
  "upi_link" text,
  "marked_paid_at" timestamptz,
  "confirmed_at" timestamptz,
  PRIMARY KEY ("settlement_id")
);
\copy synth_eval.settlements FROM 'eval/db/settlements.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_eval.transactions;
CREATE TABLE synth_eval.transactions (
  "txn_id" text,
  "user_id" text,
  "account_id" text,
  "occurred_at" timestamptz,
  "value_date" date,
  "amount_paise" bigint,
  "direction" text,
  "mode" text,
  "status" text,
  "kind" text,
  "merchant_key" text,
  "counterparty_name" text,
  "counterparty_vpa" text,
  "category_id" text,
  "narration" text,
  "ref_no" text,
  "balance_after_paise" bigint,
  "recurring_key" text,
  "transfer_pair_id" text,
  "reversal_of_id" text,
  "refund_of_id" text,
  "group_expense_id" text,
  "group_id" text,
  "settlement_id" text,
  "sms_ids" text,
  "planted_pattern" text,
  "source" text,
  PRIMARY KEY ("txn_id")
);
\copy synth_eval.transactions FROM 'eval/db/transactions.csv' WITH (FORMAT csv, HEADER true)
CREATE INDEX ON synth_eval.transactions ("user_id", "occurred_at");
CREATE INDEX ON synth_eval.transactions ("account_id", "occurred_at");

DROP TABLE IF EXISTS synth_eval.users;
CREATE TABLE synth_eval.users (
  "user_id" text,
  "persona_id" text,
  "archetype" text,
  "display_name" text,
  "first_name" text,
  "gender" text,
  "age" bigint,
  "city" text,
  "area" text,
  "language" text,
  "income_pattern" text,
  "occupation" text,
  "household" text,
  "kind" text,
  "planted_types" text,
  "seed" bigint,
  "data_start" date,
  "data_end" date,
  PRIMARY KEY ("user_id")
);
\copy synth_eval.users FROM 'eval/db/users.csv' WITH (FORMAT csv, HEADER true)

COMMIT;

-- Every row should say ok = t
SELECT tbl, expected, loaded, expected = loaded AS ok FROM (VALUES
  ('synth_eval.accounts', 550, (SELECT count(*) FROM synth_eval.accounts)),
  ('synth_eval.balance_snapshots', 148224, (SELECT count(*) FROM synth_eval.balance_snapshots)),
  ('synth_eval.card_statements', 2085, (SELECT count(*) FROM synth_eval.card_statements)),
  ('synth_eval.goal_contributions', 2000, (SELECT count(*) FROM synth_eval.goal_contributions)),
  ('synth_eval.goals', 200, (SELECT count(*) FROM synth_eval.goals)),
  ('synth_eval.group_expense_shares', 7965, (SELECT count(*) FROM synth_eval.group_expense_shares)),
  ('synth_eval.group_expenses', 2139, (SELECT count(*) FROM synth_eval.group_expenses)),
  ('synth_eval.group_invites', 30, (SELECT count(*) FROM synth_eval.group_invites)),
  ('synth_eval.group_members', 116, (SELECT count(*) FROM synth_eval.group_members)),
  ('synth_eval.groups', 30, (SELECT count(*) FROM synth_eval.groups)),
  ('synth_eval.holdings', 1483, (SELECT count(*) FROM synth_eval.holdings)),
  ('synth_eval.loans', 125, (SELECT count(*) FROM synth_eval.loans)),
  ('synth_eval.planted_patterns', 484, (SELECT count(*) FROM synth_eval.planted_patterns)),
  ('synth_eval.pockets', 891, (SELECT count(*) FROM synth_eval.pockets)),
  ('synth_eval.recurring_items', 1860, (SELECT count(*) FROM synth_eval.recurring_items)),
  ('synth_eval.settlements', 420, (SELECT count(*) FROM synth_eval.settlements)),
  ('synth_eval.transactions', 228584, (SELECT count(*) FROM synth_eval.transactions)),
  ('synth_eval.users', 200, (SELECT count(*) FROM synth_eval.users))
) v(tbl, expected, loaded) ORDER BY tbl;
