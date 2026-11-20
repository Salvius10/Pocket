"""Write the Postgres loaders for a built pack: load_demo.sql (reference + demo) and load_eval.sql.

    python -m pocket_synth.sqlgen <pack-root>

Tables land in three schemas that mirror the CSV folders 1:1 (same table and column names):
synth_ref (reference/), synth_demo (demo/db/), synth_eval (eval/db/).
Column types are inferred from every value in the file, so a load never fails on a late odd row.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

PK = {
    "users": ["user_id"], "accounts": ["account_id"], "transactions": ["txn_id"], "sms_messages": ["sms_id"],
    "card_statements": ["account_id", "statement_date"], "balance_snapshots": ["account_id", "as_of_date"],
    "goals": ["goal_id"], "pockets": ["pocket_id"], "groups": ["group_id"], "group_members": ["member_id"],
    "group_expenses": ["expense_id"], "group_expense_shares": ["expense_id", "member_id"], "settlements": ["settlement_id"],
    "group_pot_contributions": ["id"], "group_invites": ["code"], "loans": ["user_id", "key"],
    "recurring_items": ["user_id", "key"], "planted_patterns": ["user_id", "natural_key"], "profile_facts": ["user_id", "key"],
    "categories": ["category_id"], "merchants": ["merchant_key"], "banks": ["bank_code"], "cities": ["city"],
    "festivals": ["name", "start_date"], "funds": ["scheme_code"], "nav_history_synthetic": ["scheme_code", "nav_date"],
}
INDEXES = {"transactions": [["user_id", "occurred_at"], ["account_id", "occurred_at"]], "sms_messages": [["user_id", "received_at"]]}

# identifiers, references and masked numbers stay text even when they look numeric (leading zeros, long digit runs)
TEXT_NAME = re.compile(r"(^id$|_id$|_ids$|^key$|_key$|ref_no$|masked|ifsc|vpa$|code$|codes$|last4$|phone|pincode|emoji$|upi_link$)")
INT = re.compile(r"-?(0|[1-9]\d{0,17})")
NUM = re.compile(r"-?\d+\.\d+")
TSTZ = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?[+-]\d{2}:\d{2}")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def is_json(v: str) -> bool:
    if v[:1] not in "{[":
        return False
    try:
        json.loads(v)
        return True
    except ValueError:
        return False


def infer(col: str, vals: list[str]) -> str:
    if col == "scheme_code":
        return "integer"
    if TEXT_NAME.search(col):
        return "text"
    vals = [v for v in vals if v != ""]
    if not vals:
        return "text"
    for typ, ok in (("boolean", lambda v: v in ("True", "False", "true", "false")),
                    ("bigint", INT.fullmatch), ("numeric", lambda v: INT.fullmatch(v) or NUM.fullmatch(v)),
                    ("timestamptz", TSTZ.fullmatch), ("date", DATE.fullmatch), ("jsonb", is_json)):
        if all(ok(v) for v in vals):
            return typ
    return "text"


def scan(path: Path):
    with open(path, encoding="utf-8", newline="") as f:
        rd = csv.reader(f)
        header = next(rd)
        cols = [[] for _ in header]
        n = 0
        for row in rd:
            n += 1
            for i, v in enumerate(row):
                cols[i].append(v)
    return header, cols, n


def table_sql(schema: str, path: Path, rel: str):
    name = path.stem
    header, cols, n = scan(path)
    types = [infer(c, v) for c, v in zip(header, cols)]
    q = lambda c: f'"{c}"'
    lines = [f"DROP TABLE IF EXISTS {schema}.{name};"]
    body = [f"  {q(c)} {t}" for c, t in zip(header, types)]
    pk = PK.get(name)
    if pk:
        idx = [header.index(c) for c in pk]
        keys = list(zip(*[cols[i] for i in idx]))
        if len(set(keys)) == len(keys) and all(all(k) for k in keys):
            body.append(f"  PRIMARY KEY ({', '.join(q(c) for c in pk)})")
        else:
            print(f"warning: {schema}.{name}: {pk} is not unique, no primary key", file=sys.stderr)
    lines.append(f"CREATE TABLE {schema}.{name} (\n" + ",\n".join(body) + "\n);")
    lines.append(f"\\copy {schema}.{name} FROM '{rel}' WITH (FORMAT csv, HEADER true)")
    for ix in INDEXES.get(name, []):
        lines.append(f"CREATE INDEX ON {schema}.{name} ({', '.join(q(c) for c in ix)});")
    return "\n".join(lines) + "\n", (f"{schema}.{name}", n), list(zip(header, types))


def write_script(root: Path, out_name: str, parts: list[tuple[str, str]], title: str):
    out = [f"-- {title}",
           "-- Run from the pack's root folder (the one holding README.md):",
           f"--   psql \"$DATABASE_URL\" -f {out_name}",
           "-- Safe to re-run: each table is dropped and reloaded. Money is integer paise; times carry +05:30 (IST).",
           "\\set ON_ERROR_STOP on", "\\encoding UTF8", "SET client_min_messages = warning;", "BEGIN;", ""]
    counts, schema_cols = [], {}
    for schema, folder in parts:
        out.append(f"CREATE SCHEMA IF NOT EXISTS {schema};")
        for p in sorted((root / folder).glob("*.csv")):
            sql, cnt, cols = table_sql(schema, p, p.relative_to(root).as_posix())
            out.append(sql)
            counts.append(cnt)
            schema_cols[cnt[0]] = cols
    out.append("COMMIT;\n")
    out.append("-- Every row should say ok = t")
    vals = ",\n  ".join(f"('{t}', {n}, (SELECT count(*) FROM {t}))" for t, n in counts)
    out.append(f"SELECT tbl, expected, loaded, expected = loaded AS ok FROM (VALUES\n  {vals}\n) v(tbl, expected, loaded) ORDER BY tbl;")
    (root / out_name).write_text("\n".join(out) + "\n", encoding="utf-8")
    return counts, schema_cols


def main(root: Path):
    c1, s1 = write_script(root, "load_demo.sql", [("synth_ref", "reference"), ("synth_demo", "demo/db")],
                          "Pocket synthetic data: reference tables + the 6 demo personas")
    c2, s2 = write_script(root, "load_eval.sql", [("synth_eval", "eval/db")],
                          "Pocket synthetic data: the 200 evaluation users (answer key in synth_eval.planted_patterns)")
    print(f"wrote load_demo.sql ({len(c1)} tables) and load_eval.sql ({len(c2)} tables)")
    return {**s1, **s2}


if __name__ == "__main__":
    main(Path(sys.argv[1]))
