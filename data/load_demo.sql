-- Pocket synthetic data: reference tables + the 6 demo personas
-- Run from the pack's root folder (the one holding README.md):
--   psql "$DATABASE_URL" -f load_demo.sql
-- Safe to re-run: each table is dropped and reloaded. Money is integer paise; times carry +05:30 (IST).
\set ON_ERROR_STOP on
\encoding UTF8
SET client_min_messages = warning;
BEGIN;

CREATE SCHEMA IF NOT EXISTS synth_ref;
DROP TABLE IF EXISTS synth_ref.banks;
CREATE TABLE synth_ref.banks (
  "bank_code" text,
  "name" text,
  "ifsc_prefix" text,
  "sms_sender_codes" text,
  "card_sms_sender_codes" text,
  "savings_rate_bps_approx" bigint,
  "account_number_length" bigint,
  PRIMARY KEY ("bank_code")
);
\copy synth_ref.banks FROM 'reference/banks.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_ref.categories;
CREATE TABLE synth_ref.categories (
  "category_id" text,
  "kind" text,
  "default_class" text,
  "name_en" text,
  PRIMARY KEY ("category_id")
);
\copy synth_ref.categories FROM 'reference/categories.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_ref.cities;
CREATE TABLE synth_ref.cities (
  "city" text,
  "state" text,
  "region" text,
  "power_board" text,
  "power_billing" text,
  "petrol_per_litre_approx" numeric,
  "lpg_cylinder_approx" bigint,
  "metro" text,
  "areas" text,
  PRIMARY KEY ("city")
);
\copy synth_ref.cities FROM 'reference/cities.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_ref.festivals;
CREATE TABLE synth_ref.festivals (
  "name" text,
  "start_date" date,
  "end_date" date,
  "regions" text,
  "spend_multipliers" jsonb,
  PRIMARY KEY ("name", "start_date")
);
\copy synth_ref.festivals FROM 'reference/festivals.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_ref.funds;
CREATE TABLE synth_ref.funds (
  "scheme_code" integer,
  "scheme_name" text,
  "category" text,
  "latest_nav" numeric,
  "latest_nav_date" date,
  "latest_nav_source" text,
  PRIMARY KEY ("scheme_code")
);
\copy synth_ref.funds FROM 'reference/funds.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_ref.merchants;
CREATE TABLE synth_ref.merchants (
  "merchant_key" text,
  "name" text,
  "narration_name" text,
  "category_id" text,
  "subcategory" text,
  "vpa_pattern" text,
  "cities" text,
  "is_subscription_likely" boolean,
  "is_local" boolean,
  "aliases" text,
  PRIMARY KEY ("merchant_key")
);
\copy synth_ref.merchants FROM 'reference/merchants.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_ref.nav_history_synthetic;
CREATE TABLE synth_ref.nav_history_synthetic (
  "scheme_code" integer,
  "nav_date" date,
  "nav" numeric,
  "source" text,
  PRIMARY KEY ("scheme_code", "nav_date")
);
\copy synth_ref.nav_history_synthetic FROM 'reference/nav_history_synthetic.csv' WITH (FORMAT csv, HEADER true)

CREATE SCHEMA IF NOT EXISTS synth_demo;
DROP TABLE IF EXISTS synth_demo.accounts;
CREATE TABLE synth_demo.accounts (
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
\copy synth_demo.accounts FROM 'demo/db/accounts.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.balance_snapshots;
CREATE TABLE synth_demo.balance_snapshots (
  "account_id" text,
  "as_of_date" date,
  "balance_paise" bigint,
  PRIMARY KEY ("account_id", "as_of_date")
);
\copy synth_demo.balance_snapshots FROM 'demo/db/balance_snapshots.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.card_statements;
CREATE TABLE synth_demo.card_statements (
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
\copy synth_demo.card_statements FROM 'demo/db/card_statements.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.goal_contributions;
CREATE TABLE synth_demo.goal_contributions (
  "goal_id" text,
  "user_id" text,
  "amount_paise" bigint,
  "month" date,
  "source" text,
  "note" text
);
\copy synth_demo.goal_contributions FROM 'demo/db/goal_contributions.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.goals;
CREATE TABLE synth_demo.goals (
  "goal_id" text,
  "user_id" text,
  "name" text,
  "emoji" text,
  "target_paise" bigint,
  "deadline" date,
  "monthly_plan_paise" bigint,
  "priority" bigint,
  "status" text,
  "created_by" text,
  "created_at" date,
  "saved_paise" bigint,
  PRIMARY KEY ("goal_id")
);
\copy synth_demo.goals FROM 'demo/db/goals.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.group_expense_shares;
CREATE TABLE synth_demo.group_expense_shares (
  "expense_id" text,
  "member_id" text,
  "share_paise" bigint,
  PRIMARY KEY ("expense_id", "member_id")
);
\copy synth_demo.group_expense_shares FROM 'demo/db/group_expense_shares.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.group_expenses;
CREATE TABLE synth_demo.group_expenses (
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
\copy synth_demo.group_expenses FROM 'demo/db/group_expenses.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.group_invites;
CREATE TABLE synth_demo.group_invites (
  "group_id" text,
  "created_by" text,
  "max_uses" bigint,
  "code" text,
  "expires_at" date,
  "uses" bigint,
  PRIMARY KEY ("code")
);
\copy synth_demo.group_invites FROM 'demo/db/group_invites.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.group_members;
CREATE TABLE synth_demo.group_members (
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
\copy synth_demo.group_members FROM 'demo/db/group_members.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.group_pot_contributions;
CREATE TABLE synth_demo.group_pot_contributions (
  "group_id" text,
  "id" text,
  "member_id" text,
  "amount_paise" bigint,
  "method" text,
  "note" text,
  "occurred_at" timestamptz,
  PRIMARY KEY ("id")
);
\copy synth_demo.group_pot_contributions FROM 'demo/db/group_pot_contributions.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.groups;
CREATE TABLE synth_demo.groups (
  "group_id" text,
  "key" text,
  "type" text,
  "name" text,
  "emoji" text,
  "owner_user_id" text,
  "created_at" date,
  "budget_monthly_paise" bigint,
  "pot_target_paise" bigint,
  "pot_deadline" date,
  "status" text,
  PRIMARY KEY ("group_id")
);
\copy synth_demo.groups FROM 'demo/db/groups.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.holdings;
CREATE TABLE synth_demo.holdings (
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
  "gold_grams" numeric,
  "balance_paise" bigint,
  "balance_as_of" date,
  "booked_by" text,
  "latest_nav" numeric,
  "latest_nav_date" date,
  "value_at_latest_nav_paise" bigint
);
\copy synth_demo.holdings FROM 'demo/db/holdings.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.loans;
CREATE TABLE synth_demo.loans (
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
\copy synth_demo.loans FROM 'demo/db/loans.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.planted_patterns;
CREATE TABLE synth_demo.planted_patterns (
  "user_id" text,
  "pattern_type" text,
  "natural_key" text,
  "merchant_key" text,
  "mandate_txn_id" text,
  "mandate_date" date,
  "mandate_amount_paise" bigint,
  "first_charge_date" date,
  "monthly_amount_paise" bigint,
  "charges" bigint,
  "total_paid_paise" bigint,
  "account_id" text,
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
  "first_txn_id" text,
  "second_txn_id" text,
  "amount_paise" bigint,
  "first_at" timestamptz,
  "second_at" timestamptz,
  "both_posted" boolean,
  "account_masked" text,
  "bank" text,
  "min_balance_60d_paise" bigint,
  "avg_monthly_outflow_paise" bigint,
  "buffer_paise" bigint,
  "idle_paise" bigint,
  "threshold_paise" bigint,
  "flagged" boolean,
  "definition" text,
  "card_masked" text,
  "monthly_rate_bps" bigint,
  "finance_charge_txn_ids" text,
  "finance_charges_paise" bigint,
  "last_charge_date" date,
  "outstanding_at_end_paise" bigint,
  "revolving_statements" text,
  PRIMARY KEY ("user_id", "natural_key")
);
\copy synth_demo.planted_patterns FROM 'demo/db/planted_patterns.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.pockets;
CREATE TABLE synth_demo.pockets (
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
\copy synth_demo.pockets FROM 'demo/db/pockets.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.profile_facts;
CREATE TABLE synth_demo.profile_facts (
  "user_id" text,
  "key" text,
  "value" text,
  "source" text,
  "language" text,
  PRIMARY KEY ("user_id", "key")
);
\copy synth_demo.profile_facts FROM 'demo/db/profile_facts.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.recurring_items;
CREATE TABLE synth_demo.recurring_items (
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
\copy synth_demo.recurring_items FROM 'demo/db/recurring_items.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.settlements;
CREATE TABLE synth_demo.settlements (
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
\copy synth_demo.settlements FROM 'demo/db/settlements.csv' WITH (FORMAT csv, HEADER true)

DROP TABLE IF EXISTS synth_demo.sms_messages;
CREATE TABLE synth_demo.sms_messages (
  "sms_id" text,
  "user_id" text,
  "sender_id" text,
  "body" text,
  "received_at" timestamptz,
  "template_id" text,
  "holdout" boolean,
  "transaction_id" text,
  "ground_truth" jsonb,
  PRIMARY KEY ("sms_id")
);
\copy synth_demo.sms_messages FROM 'demo/db/sms_messages.csv' WITH (FORMAT csv, HEADER true)
CREATE INDEX ON synth_demo.sms_messages ("user_id", "received_at");

DROP TABLE IF EXISTS synth_demo.transactions;
CREATE TABLE synth_demo.transactions (
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
\copy synth_demo.transactions FROM 'demo/db/transactions.csv' WITH (FORMAT csv, HEADER true)
CREATE INDEX ON synth_demo.transactions ("user_id", "occurred_at");
CREATE INDEX ON synth_demo.transactions ("account_id", "occurred_at");

DROP TABLE IF EXISTS synth_demo.users;
CREATE TABLE synth_demo.users (
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
\copy synth_demo.users FROM 'demo/db/users.csv' WITH (FORMAT csv, HEADER true)

COMMIT;

-- Every row should say ok = t
SELECT tbl, expected, loaded, expected = loaded AS ok FROM (VALUES
  ('synth_ref.banks', 7, (SELECT count(*) FROM synth_ref.banks)),
  ('synth_ref.categories', 38, (SELECT count(*) FROM synth_ref.categories)),
  ('synth_ref.cities', 15, (SELECT count(*) FROM synth_ref.cities)),
  ('synth_ref.festivals', 24, (SELECT count(*) FROM synth_ref.festivals)),
  ('synth_ref.funds', 16, (SELECT count(*) FROM synth_ref.funds)),
  ('synth_ref.merchants', 325, (SELECT count(*) FROM synth_ref.merchants)),
  ('synth_ref.nav_history_synthetic', 4752, (SELECT count(*) FROM synth_ref.nav_history_synthetic)),
  ('synth_demo.accounts', 18, (SELECT count(*) FROM synth_demo.accounts)),
  ('synth_demo.balance_snapshots', 4608, (SELECT count(*) FROM synth_demo.balance_snapshots)),
  ('synth_demo.card_statements', 77, (SELECT count(*) FROM synth_demo.card_statements)),
  ('synth_demo.goal_contributions', 207, (SELECT count(*) FROM synth_demo.goal_contributions)),
  ('synth_demo.goals', 12, (SELECT count(*) FROM synth_demo.goals)),
  ('synth_demo.group_expense_shares', 1584, (SELECT count(*) FROM synth_demo.group_expense_shares)),
  ('synth_demo.group_expenses', 504, (SELECT count(*) FROM synth_demo.group_expenses)),
  ('synth_demo.group_invites', 6, (SELECT count(*) FROM synth_demo.group_invites)),
  ('synth_demo.group_members', 22, (SELECT count(*) FROM synth_demo.group_members)),
  ('synth_demo.group_pot_contributions', 24, (SELECT count(*) FROM synth_demo.group_pot_contributions)),
  ('synth_demo.groups', 6, (SELECT count(*) FROM synth_demo.groups)),
  ('synth_demo.holdings', 35, (SELECT count(*) FROM synth_demo.holdings)),
  ('synth_demo.loans', 5, (SELECT count(*) FROM synth_demo.loans)),
  ('synth_demo.planted_patterns', 36, (SELECT count(*) FROM synth_demo.planted_patterns)),
  ('synth_demo.pockets', 33, (SELECT count(*) FROM synth_demo.pockets)),
  ('synth_demo.profile_facts', 30, (SELECT count(*) FROM synth_demo.profile_facts)),
  ('synth_demo.recurring_items', 75, (SELECT count(*) FROM synth_demo.recurring_items)),
  ('synth_demo.settlements', 56, (SELECT count(*) FROM synth_demo.settlements)),
  ('synth_demo.sms_messages', 7443, (SELECT count(*) FROM synth_demo.sms_messages)),
  ('synth_demo.transactions', 7379, (SELECT count(*) FROM synth_demo.transactions)),
  ('synth_demo.users', 6, (SELECT count(*) FROM synth_demo.users))
) v(tbl, expected, loaded) ORDER BY tbl;
