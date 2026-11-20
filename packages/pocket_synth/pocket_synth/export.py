"""Build everything and write the dataset.

    python -m pocket_synth.export --out ../data
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from . import refdata as R
from .content import CATALOG, layouts, test_chats
from .engine import ALIASES, Builder, P, add_months, month_starts, uid
from .groups import build_groups, link_household
from .nav import build_nav
from .population import demo_specs, eval_specs
from .render import Renderer

NO_SMS = {"fd_book", "fd_maturity", "interest", "charge", "fin_charge", "fin_charge_gst"}
M_END = date(R.END.year, R.END.month, 1)


def money(paise):
    return None if paise is None else int(paise)


# ---------------------------------------------------------------------------------------------- answer key
def month_totals(b, category):
    tot = defaultdict(int)
    for t in b.accepted:
        if t.category == category and t.status == "success":
            key = t.ts.strftime("%Y-%m")
            if t.direction == "debit":
                tot[key] += t.amount
    for t in b.accepted:
        if t.category == "refund" and t.refund_of:
            orig = next((x for x in b.accepted if x.id == t.refund_of), None)
            if orig and orig.category == category:
                tot[t.ts.strftime("%Y-%m")] -= t.amount
    return tot


def account_outflow(b, acc_id):
    out = defaultdict(int)
    for t in b.accepted:
        if t.account_id == acc_id and t.direction == "debit" and t.status == "success":
            out[t.ts.strftime("%Y-%m")] += t.amount
    months = [add_months(M_END, -k).strftime("%Y-%m") for k in (1, 2, 3)]
    return sum(out[m] for m in months) / 3


def idle_metrics(b, acc):
    lo = R.END - timedelta(days=59)
    vals = [v for d, v in acc.eod.items() if lo <= d <= R.END]
    min_bal = min(vals) if vals else 0
    avg_out = account_outflow(b, acc.id)
    buffer = 1.5 * avg_out
    idle = min_bal - buffer
    threshold = max(P(25000), 0.5 * avg_out)
    return dict(min_balance_60d_paise=int(min_bal), avg_monthly_outflow_paise=int(avg_out), buffer_paise=int(buffer),
                idle_paise=int(idle // P(1000) * P(1000)) if idle > 0 else 0, threshold_paise=int(threshold), flagged=idle >= threshold)


def recurring_series(b, key):
    return sorted([t for t in b.accepted if t.recurring_key == key and t.direction == "debit" and t.status == "success"], key=lambda t: t.ts)


def answer_key(b):
    s = b.s
    out = []
    p = s.planted
    if "forgotten_subscription" in p:
        mk = p["forgotten_subscription"]["merchant_key"]
        key = f"sub_{mk}"
        mandate = [t for t in b.accepted if t.recurring_key == key + ":mandate"]
        charges = recurring_series(b, key)
        out.append(dict(pattern_type="forgotten_subscription", natural_key=f"forgotten_sub:{mk}", merchant_key=mk,
                        mandate_txn_id=mandate[0].id if mandate else None, mandate_date=mandate[0].ts.date().isoformat() if mandate else None,
                        mandate_amount_paise=mandate[0].amount if mandate else None, first_charge_date=charges[0].ts.date().isoformat() if charges else None,
                        monthly_amount_paise=charges[-1].amount if charges else None, charges=len(charges),
                        total_paid_paise=sum(t.amount for t in charges), account_id=charges[0].account_id if charges else None))
    if "price_hike" in p:
        ph = p["price_hike"]
        ser = recurring_series(b, ph["recurring_key"])
        new = P(ph["new_amount"])
        first_new = next((t for t in ser if t.amount == new), None)
        prev = [t.amount for t in ser if t.amount != new][-3:]
        out.append(dict(pattern_type="price_hike", natural_key=f"price_hike:{ph['merchant_key']}:{new}", merchant_key=ph["merchant_key"],
                        recurring_key=ph["recurring_key"], old_amount_paise=int(statistics.median(prev)) if prev else None, new_amount_paise=new,
                        first_new_charge_date=first_new.ts.date().isoformat() if first_new else None, latest_txn_id=ser[-1].id if ser else None,
                        increase_pct=round(100 * (new - statistics.median(prev)) / statistics.median(prev)) if prev else None))
    if "category_creep" in p:
        tot = month_totals(b, "food_delivery")
        e = [tot[m] for m in ("2026-05", "2026-06", "2026-07")]
        rcn = [tot[m] for m in ("2026-08", "2026-09", "2026-10")]
        ea, ra = sum(e) / 3, sum(rcn) / 3
        out.append(dict(pattern_type="category_creep", natural_key=f"creep:food_delivery:{M_END.strftime('%Y-%m')}", category_id="food_delivery",
                        earlier_months="2026-05,2026-06,2026-07", recent_months="2026-08,2026-09,2026-10", earlier_avg_paise=int(ea),
                        recent_avg_paise=int(ra), increase_pct=round(100 * (ra - ea) / ea) if ea else None,
                        this_month_to_date_paise=tot[M_END.strftime("%Y-%m")]))
    if "duplicate_charge" in p:
        d = next(x for x in b.planted if x["pattern_type"] == "duplicate_charge")
        ids = {t.id for t in b.accepted}
        out.append(dict(pattern_type="duplicate_charge", natural_key=f"dup:{d['second_txn_id']}", merchant_key=d["merchant_key"],
                        first_txn_id=d["first_txn_id"], second_txn_id=d["second_txn_id"], amount_paise=d["amount_paise"],
                        account_id=d["account_id"], first_at=d["first_at"], second_at=d["second_at"],
                        both_posted=d["first_txn_id"] in ids and d["second_txn_id"] in ids))
    if "idle_cash" in p:
        acc = b.accounts[p["idle_cash"]["account_role"]]
        m = idle_metrics(b, acc)
        out.append(dict(pattern_type="idle_cash", natural_key=f"idle:{acc.id}:{M_END.strftime('%Y-%m')}", account_id=acc.id,
                        account_masked=acc.masked, bank=acc.bank, **m,
                        definition="idle = min end-of-day balance over last 60 days - 1.5 x this account's avg monthly outflow (last 3 complete months); flagged if >= max(Rs 25,000, 0.5 x outflow)"))
    if "expensive_card_balance" in p:
        card = b.card
        fc = [t for t in b.accepted if t.account_id == card.id and t.kind in ("fin_charge", "fin_charge_gst")]
        out.append(dict(pattern_type="expensive_card_balance", natural_key=f"card_revolve:{card.id}:{M_END.strftime('%Y-%m')}", account_id=card.id,
                        card_masked=card.masked, bank=card.bank, monthly_rate_bps=card.card_rate_bps // 12,
                        finance_charge_txn_ids=",".join(t.id for t in fc), finance_charges_paise=sum(t.amount for t in fc),
                        last_charge_date=max((t.ts.date() for t in fc), default=None).isoformat() if fc else None,
                        outstanding_at_end_paise=card.balance,
                        revolving_statements=",".join(s.revolve_statements)))
    return out


def negative_checks(b) -> Counter:
    """Signals of each planted type in a user who did NOT get that plant (should all be zero)."""
    c = Counter()
    p = b.s.planted
    if "forgotten_subscription" not in p:
        c["forgotten_subscription"] += sum(1 for t in b.accepted if t.direction == "debit" and t.amount <= P(5) and t.merchant_key
                                           and R.MERCHANT_BY_KEY.get(t.merchant_key, {}).get("is_subscription_likely"))
    if "price_hike" not in p:
        for key, meta in b.recurring_out.items():
            if meta["amount_is_variable"] or meta["kind"] in ("sip", "emi", "rent", "salary"):
                continue
            ser = recurring_series(b, key)
            if len(ser) >= 4 and ser[-1].ts.date() >= R.END - timedelta(days=45):
                prev = statistics.median([t.amount for t in ser[-4:-1]])
                if ser[-1].amount >= 1.10 * prev and ser[-1].amount - prev >= P(20):
                    c["price_hike"] += 1
    if "category_creep" not in p:
        tot = month_totals(b, "food_delivery")
        e = sum(tot[m] for m in ("2026-05", "2026-06", "2026-07")) / 3
        rr = sum(tot[m] for m in ("2026-08", "2026-09", "2026-10")) / 3
        if e and rr >= 1.25 * e and rr - e >= P(1000):
            c["category_creep"] += 1
    if "duplicate_charge" not in p:
        key = defaultdict(list)
        for t in b.accepted:
            if t.direction == "debit" and t.status == "success" and t.amount >= P(100):
                key[(t.account_id, t.merchant_key or t.cp_vpa or t.cp_name, t.amount)].append(t.ts)
        for v in key.values():
            v.sort()
            c["duplicate_charge"] += sum(1 for a, z in zip(v, v[1:]) if (z - a) <= timedelta(minutes=10))
    if "idle_cash" not in p:
        for acc in b.accounts.values():
            if acc.type == "savings" and idle_metrics(b, acc)["flagged"]:
                c["idle_cash"] += 1
    if "expensive_card_balance" not in p:
        c["expensive_card_balance"] += sum(1 for t in b.accepted if t.kind == "fin_charge")
    return c


# ---------------------------------------------------------------------------------------------- writers
def write_csv(path: Path, rows: list[dict], gz: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    cols = list(rows[0].keys())
    for r in rows[1:]:
        for k in r:
            if k not in cols:
                cols.append(k)
    opener = (lambda p: gzip.open(p, "wt", encoding="utf-8", newline="")) if gz else (lambda p: open(p, "w", encoding="utf-8", newline=""))
    with opener(path.with_suffix(path.suffix + ".gz") if gz else path) as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in r.items()})


def write_jsonl(path: Path, rows: list[dict], gz: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path.with_suffix(path.suffix + ".gz") if gz else path
    with open(target, "wb") as raw:
        # mtime=0 and no stored file name keep .gz output byte-identical across runs
        z = gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) if gz else None
        with io.TextIOWrapper(z or raw, encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


def tables_for(builders, groups, link_ids):
    T = defaultdict(list)
    for b in builders:
        s = b.s
        T["users"].append(dict(user_id=s.user_id, persona_id=s.persona_id, archetype=s.archetype, display_name=s.full_name, first_name=s.first_name,
                               gender=s.gender, age=s.age, city=s.city, area=s.area, language=s.language, income_pattern=s.income_pattern,
                               occupation=s.occupation, household=s.household, kind="demo" if s.persona_id else "synthetic_eval",
                               planted_types="|".join(sorted(s.planted)), seed=s.seed, data_start=R.START.isoformat(), data_end=R.END.isoformat()))
        for k, v in (s.profile or {}).items():
            T["profile_facts"].append(dict(user_id=s.user_id, key=k, value=v, source="onboarding", language=s.language))
        for acc in b.accounts.values():
            T["accounts"].append(dict(account_id=acc.id, user_id=s.user_id, role=acc.role, provider="synthetic", institution_code=acc.bank,
                                      institution_name=R.BANKS[acc.bank]["name"], type=acc.type, masked_number=acc.masked, ifsc=acc.ifsc if acc.type != "credit_card" else None,
                                      nickname=acc.nickname, opened_on=acc.opened.isoformat(), opening_balance_paise=acc.opening_balance,
                                      current_balance_paise=acc.balance, balance_as_of=f"{R.END.isoformat()}T23:59:59+05:30",
                                      credit_limit_paise=acc.card_limit, interest_rate_bps=acc.card_rate_bps if acc.type == "credit_card" else R.BANKS[acc.bank]["rate_bps"],
                                      statement_day=acc.statement_day, due_day=((acc.statement_day + 20 - 1) % 28) + 1 if acc.statement_day else None))
            for st in acc.statements:
                T["card_statements"].append(dict(account_id=acc.id, user_id=s.user_id, **st))
            if acc.type in ("savings", "current"):
                for d, v in sorted(acc.eod.items()):
                    T["balance_snapshots"].append(dict(account_id=acc.id, as_of_date=d.isoformat(), balance_paise=v))
        for t in b.accepted:
            rev = t.kind == "upi_reversal" or (t.status == "reversed" and t.direction == "debit")
            T["transactions"].append(dict(
                txn_id=t.id, user_id=s.user_id, account_id=t.account_id, occurred_at=t.ts.isoformat(), value_date=t.ts.date().isoformat(),
                amount_paise=t.amount, direction=t.direction, mode=t.mode, status=t.status, kind=t.kind, merchant_key=t.merchant_key,
                counterparty_name=t.cp_name, counterparty_vpa=t.cp_vpa, category_id=t.category, narration=t.narration, ref_no=t.ref,
                balance_after_paise=t.balance_after, recurring_key=t.recurring_key,
                transfer_pair_id=None if rev else t.transfer_pair, reversal_of_id=t.refund_of if t.kind == "upi_reversal" else None,
                refund_of_id=t.refund_of if t.category == "refund" else None, group_expense_id=t.group_expense_id,
                group_id=t.meta.get("group"), settlement_id=t.meta.get("settlement_id"), sms_ids="|".join(t.sms_ids) or None,
                planted_pattern=t.planted, source="aa"))
        for key, m in b.recurring_out.items():
            T["recurring_items"].append(dict(user_id=s.user_id, **m))
        for ln in b.loans:
            T["loans"].append(dict(user_id=s.user_id, **ln))
        for h in b.holdings + s.static_holdings:
            row = dict(user_id=s.user_id, kind=h["kind"], name=h["name"], scheme_code=h.get("scheme_code"), units=h.get("units"),
                       invested_paise=h.get("invested_paise"), sip_amount_paise=h.get("sip_amount_paise"), sip_day=h.get("sip_day"),
                       folio_masked=("XXXX" + h["folio"][-6:]) if h.get("folio") else None, platform=h.get("platform"),
                       fd_principal_paise=h.get("fd_principal_paise"), fd_rate_bps=h.get("fd_rate_bps"), fd_start_date=h.get("fd_start_date"),
                       fd_maturity_date=h.get("fd_maturity_date"), gold_grams=h.get("gold_grams"), balance_paise=h.get("balance_paise"),
                       balance_as_of=h.get("balance_as_of"), booked_by=h.get("booked_by"))
            if h["kind"] == "mutual_fund":
                f = R.FUND_BY_CODE[h["scheme_code"]]
                row["latest_nav"], row["latest_nav_date"] = f[3], f[4].isoformat()
                row["value_at_latest_nav_paise"] = int(round(h["units"] * f[3] * 100))
            T["holdings"].append(row)
        for i, pk in enumerate(s.pockets):
            T["pockets"].append(dict(pocket_id=uid(s.user_id, "pocket", i), user_id=s.user_id, name=pk["name"], emoji=pk["emoji"],
                                     monthly_limit_paise=P(pk["limit"]), category_ids="|".join(pk["categories"]), status="active", sort_order=i,
                                     created_by="loader", created_at="2026-06-01"))
        for i, gl in enumerate(s.goals):
            gid = uid(s.user_id, "goal", i)
            T["goals"].append(dict(goal_id=gid, user_id=s.user_id, name=gl["name"], emoji=gl["emoji"], target_paise=P(gl["target"]),
                                   deadline=gl["deadline"], monthly_plan_paise=P(gl["monthly_plan"]) if gl["monthly_plan"] else None,
                                   priority=gl["priority"], status="active", created_by="loader", created_at=gl["start"],
                                   saved_paise=P(gl["saved"])))
            months = list(month_starts(date.fromisoformat(gl["start"]), R.END))
            opening = P(gl["saved"]) // 2
            per = (P(gl["saved"]) - opening) // max(1, len(months))
            T["goal_contributions"].append(dict(goal_id=gid, user_id=s.user_id, amount_paise=opening + (P(gl["saved"]) - opening - per * len(months)),
                                                month=months[0].isoformat() if months else gl["start"], source="loader", note="Already saved at setup"))
            for ms in months:
                T["goal_contributions"].append(dict(goal_id=gid, user_id=s.user_id, amount_paise=per, month=ms.isoformat(), source="loader", note="Monthly"))
        for row in answer_key(b):
            T["planted_patterns"].append(dict(user_id=s.user_id, **{k: (v if not isinstance(v, bool) else str(v).lower()) for k, v in row.items()}))
    for g in groups:
        T["groups"].append(dict(group_id=g["group_id"], key=g["key"], type=g["type"], name=g["name"], emoji=g["emoji"], owner_user_id=g["owner_user_id"],
                                created_at=g["created_at"], budget_monthly_paise=g["budget_monthly_paise"], pot_target_paise=g["pot_target_paise"],
                                pot_deadline=g["pot_deadline"], status=g["status"]))
        for m in g["members"]:
            T["group_members"].append(dict(member_id=m["member_id"], group_id=g["group_id"], user_id=m["user_id"], display_name=m["display_name"],
                                           vpa=m["vpa"], role=m["role"], join_order=m["join_order"], sharing=m["sharing"]))
        for e in g["expenses"]:
            T["group_expenses"].append(dict(expense_id=e["expense_id"], group_id=g["group_id"], paid_by_member_id=e["paid_by_member_id"],
                                            amount_paise=e["amount_paise"], description=e["description"], category_id=e["category_id"],
                                            occurred_at=e["occurred_at"], split_method=e["split_method"], split_input=e["split_input"],
                                            linked_transaction_id=e["linked_transaction_id"] or link_ids.get(e["expense_id"]),
                                            created_by_member_id=e["created_by_member_id"], is_deleted=False))
            for sh in e["shares"]:
                T["group_expense_shares"].append(dict(expense_id=e["expense_id"], **sh))
        for st in g["settlements"]:
            T["settlements"].append(dict(group_id=g["group_id"], **st))
        for pc in g["pot_contributions"]:
            T["group_pot_contributions"].append(dict(group_id=g["group_id"], **pc))
        for inv in g["invites"]:
            T["group_invites"].append(dict(group_id=g["group_id"], created_by=g["owner_user_id"], max_uses=10, **inv))
    return T


def run(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    nav = build_nav()
    demo, evals = demo_specs(), eval_specs()
    gm = build_groups(demo, evals)
    builders = {}
    for s in demo + evals:
        builders[s.user_id] = Builder(s, nav, gm.events.get(s.user_id, [])).build()
    for req in gm.link_requests:
        link_household(gm, builders[req["user_id"]], req)
    # link ids from ledger side (expense created by app user payment -> ledger txn)
    link_ids = {}
    for b in builders.values():
        for t in b.accepted:
            if t.group_expense_id and t.direction == "debit":
                link_ids.setdefault(t.group_expense_id, t.id)
    sms = defaultdict(list)
    aa = defaultdict(list)
    for uid_, b in builders.items():
        rend = Renderer(b, b.s.seed)
        for t in b.accepted:
            acc = b.by_id[t.account_id]
            t.narration = rend.narrate(t, acc)
            if t.kind not in NO_SMS and t.mode != "cash_manual":
                rend.sms_for(t, acc)
        rend.noise_sms()
        sms[uid_] = sorted(rend.sms, key=lambda x: x["received_at"])
        for acc in b.accounts.values():
            txns = [t for t in b.accepted if t.account_id == acc.id]
            aa[uid_].append(rend.aa_json(acc, txns))
    demo_b = [builders[s.user_id] for s in demo]
    eval_b = [builders[s.user_id] for s in evals]
    demo_groups = [g for g in gm.groups if g["key"].startswith("demo_")]
    eval_groups = [g for g in gm.groups if not g["key"].startswith("demo_")]

    # ---- reference
    ref = out / "reference"
    write_csv(ref / "categories.csv", [dict(category_id=c, kind=k, default_class=d, name_en=n) for c, k, d, n in R.CATEGORIES])
    write_csv(ref / "merchants.csv", [dict(merchant_key=m["key"], name=m["name"], narration_name=m["narr"], category_id=m["category"],
                                           subcategory=m["subcategory"], vpa_pattern=m["vpa"], cities="|".join(m["cities"]) if m["cities"] else "*",
                                           is_subscription_likely=m["is_subscription_likely"], is_local=m["local"],
                                           aliases="|".join(ALIASES.get(m["key"], []))) for m in R.MERCHANTS])
    write_csv(ref / "banks.csv", [dict(bank_code=k, name=v["name"], ifsc_prefix=v["ifsc"], sms_sender_codes="|".join(v["sms"]),
                                       card_sms_sender_codes="|".join(v["card_sms"]), savings_rate_bps_approx=v["rate_bps"],
                                       account_number_length=v["acct_len"]) for k, v in R.BANKS.items()])
    write_csv(ref / "cities.csv", [dict(city=c, state=v["state"], region=v["region"], power_board=v["power"], power_billing=v["bill"],
                                        petrol_per_litre_approx=v["petrol"], lpg_cylinder_approx=v["lpg"], metro=v["metro"], areas="|".join(v["areas"]))
                                   for c, v in R.CITIES.items()])
    write_csv(ref / "festivals.csv", [dict(name=n, start_date=a.isoformat(), end_date=b.isoformat(), regions="|".join(r) if r else "*",
                                           spend_multipliers=json.dumps(e)) for n, a, b, r, e in R.FESTIVALS])
    write_csv(ref / "funds.csv", [dict(scheme_code=c, scheme_name=n, category=cat, latest_nav=nv, latest_nav_date=d.isoformat(),
                                       latest_nav_source="AMFI via mfapi.in, checked 20 Nov 2026") for c, n, cat, nv, d, *_ in R.FUNDS])
    write_csv(ref / "nav_history_synthetic.csv", [dict(scheme_code=c, nav_date=d.isoformat(), nav=v,
                                                       source="amfi" if d == R.FUND_BY_CODE[c][4] else "synthetic_backfill")
                                                  for c, ser in nav.items() for d, v in sorted(ser.items())])

    # ---- demo
    T = tables_for(demo_b, demo_groups, link_ids)
    for name, rows in T.items():
        write_csv(out / "demo" / "db" / f"{name}.csv", rows)
    for b in demo_b:
        pid = b.s.persona_id
        for doc in aa[b.s.user_id]:
            a = doc["Account"]
            masked = a.get("maskedAccNumber") or a.get("maskedCardNumber")
            p = out / "demo" / "sources" / pid / "account_aggregator" / f"{a['type']}_{masked[-4:]}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(doc, ensure_ascii=False, indent=1, default=str))
        write_jsonl(out / "demo" / "sources" / pid / "sms.jsonl", sms[b.s.user_id])
    write_csv(out / "demo" / "db" / "sms_messages.csv", [dict(sms_id=x["sms_id"], user_id=x["user_id"], sender_id=x["sender_id"], body=x["body"],
                                                              received_at=x["received_at"], template_id=x["template_id"], holdout=x["holdout"],
                                                              transaction_id=x["transaction_id"], ground_truth=x["ground_truth"])
                                                         for b in demo_b for x in sms[b.s.user_id]])
    (out / "demo" / "groups.json").write_text(json.dumps([{k: v for k, v in g.items()} for g in demo_groups], ensure_ascii=False, indent=1, default=str))

    # ---- eval
    TE = tables_for(eval_b, eval_groups, link_ids)
    for name, rows in TE.items():
        write_csv(out / "eval" / "db" / f"{name}.csv", rows)
    write_jsonl(out / "eval" / "sources" / "sms.jsonl", [x for b in eval_b for x in sms[b.s.user_id]], gz=True)
    write_jsonl(out / "eval" / "sources" / "account_aggregator.jsonl", [dict(user_id=b.s.user_id, statement=doc) for b in eval_b for doc in aa[b.s.user_id]], gz=True)

    # ---- content
    group_ids = {g["key"]: g["group_id"] for g in demo_groups}
    ideal, variants = layouts(group_ids)
    write_jsonl(out / "content" / "test_chats.jsonl", test_chats())
    (out / "content" / "ideal_layouts.json").write_text(json.dumps(ideal, ensure_ascii=False, indent=1))
    (out / "content" / "layout_variants.json").write_text(json.dumps(variants, ensure_ascii=False, indent=1))
    (out / "content" / "widget_catalog.json").write_text(json.dumps(CATALOG, indent=1))

    # ---- excel workbook for humans (demo only)
    excel(out / "demo" / "demo_personas.xlsx", T, sms, demo_b)

    # ---- validation
    report = validate(demo_b, eval_b, builders, T, TE, sms, gm)
    (out / "validation_report.md").write_text(report)
    return report


def excel(path, T, sms, demo_b):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    wb.remove(wb.active)
    names = {b.s.user_id: b.s.first_name for b in demo_b}
    acct_label = {a["account_id"]: f"{a['institution_code']} {a['type']} ••{a['masked_number'][-4:]}" for a in T["accounts"]}
    sheets = [
        ("Personas", T["users"], ["display_name", "persona_id", "age", "city", "area", "language", "occupation", "income_pattern", "household", "planted_types"]),
        ("Accounts", T["accounts"], ["user_id", "institution_name", "type", "masked_number", "opening_balance_paise", "current_balance_paise", "credit_limit_paise", "statement_day"]),
        ("Transactions", T["transactions"], ["user_id", "occurred_at", "account_id", "direction", "amount_paise", "mode", "status", "category_id", "counterparty_name", "narration", "ref_no", "balance_after_paise", "planted_pattern"]),
        ("Recurring", T["recurring_items"], ["user_id", "name", "kind", "category", "amount_paise", "cadence", "day", "channel", "planted"]),
        ("Loans", T["loans"], ["user_id", "lender", "loan_type", "principal_paise", "outstanding_paise", "interest_rate_bps", "emi_paise", "emi_day", "months_left"]),
        ("Holdings", T["holdings"], ["user_id", "kind", "name", "scheme_code", "units", "invested_paise", "value_at_latest_nav_paise", "sip_amount_paise", "fd_principal_paise", "gold_grams", "balance_paise"]),
        ("Pockets", T["pockets"], ["user_id", "name", "emoji", "monthly_limit_paise", "category_ids"]),
        ("Goals", T["goals"], ["user_id", "name", "emoji", "target_paise", "saved_paise", "deadline", "monthly_plan_paise"]),
        ("Planted answer key", T["planted_patterns"], None),
        ("Group expenses", T["group_expenses"], ["group_id", "occurred_at", "description", "amount_paise", "split_method", "paid_by_member_id", "linked_transaction_id"]),
        ("Settlements", T["settlements"], ["group_id", "from_member_id", "to_member_id", "amount_paise", "status", "created_at", "upi_link"]),
        ("SMS sample", [x for b in demo_b for x in sms[b.s.user_id][:120]], ["user_id", "received_at", "sender_id", "body", "template_id", "transaction_id"]),
    ]
    head = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="1F6F5C")
    for title, rows, cols in sheets:
        ws = wb.create_sheet(title[:31])
        cols = cols or (list(rows[0].keys()) if rows else [])
        disp = [("person" if c == "user_id" else "account" if c == "account_id" else c.replace("_paise", " (₹)")) for c in cols]
        ws.append(disp)
        for c in ws[1]:
            c.font, c.fill = head, fill
        for r in rows:
            vals = []
            for c in cols:
                v = r.get(c)
                if c == "user_id":
                    v = names.get(v, v)
                elif c == "account_id":
                    v = acct_label.get(v, v)
                elif c.endswith("_paise") and isinstance(v, int):
                    v = round(v / 100, 2)
                elif isinstance(v, (dict, list)):
                    v = json.dumps(v, ensure_ascii=False)
                elif v is not None and not isinstance(v, (int, float, bool)):
                    v = str(v)
                vals.append(v)
            ws.append(vals)
        for i, c in enumerate(cols, 1):
            ws.column_dimensions[get_column_letter(i)].width = min(60, max(12, len(disp[i - 1]) + 4))
        ws.freeze_panes = "A2"
    wb.save(path)


def validate(demo_b, eval_b, builders, T, TE, sms, gm) -> str:
    L = ["# Validation report", "", f"Window: {R.START} to {R.END} (IST). Generated deterministically from fixed seeds.", ""]

    def per_user_rows(b):
        months = defaultdict(int)
        for t in b.accepted:
            months[t.ts.strftime("%Y-%m")] += 1
        full = [v for k, v in months.items() if k != R.END.strftime("%Y-%m")]
        neg = sum(1 for a in b.accounts.values() if a.type in ("savings", "current") and min(a.eod.values()) < 0)
        upi = [t for t in b.accepted if t.mode in ("upi", "autopay") and t.direction == "debit" and t.status == "success"]
        debits = [t for t in b.accepted if t.direction == "debit" and t.status == "success"]
        return dict(min_m=min(full), max_m=max(full), neg=neg, n=len(b.accepted), upi_share=len(upi) / max(1, len(debits)),
                    upi_amounts=[t.amount for t in upi])

    L += ["## Demo personas", "", "| Persona | Txns | Per month (min–max) | UPI share of debits | Median UPI debit | Negative balances | Dropped (insufficient funds) | Top-ups |",
          "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for b in demo_b:
        u = per_user_rows(b)
        med = statistics.median(u["upi_amounts"]) / 100 if u["upi_amounts"] else 0
        L.append(f"| {b.s.persona_id} ({b.s.first_name}) | {u['n']} | {u['min_m']}–{u['max_m']} | {u['upi_share']:.0%} | ₹{med:,.0f} | {u['neg']} | "
                 f"{b.stats['insufficient_drop']} | {b.stats['topup_self'] + b.stats['topup_family']} |")
    allu = [per_user_rows(b) for b in eval_b]
    L += ["", "## 200 evaluation users", "",
          f"- Transactions: {sum(u['n'] for u in allu):,}; per user per full month: min {min(u['min_m'] for u in allu)}, "
          f"median {statistics.median([statistics.median([u['min_m'], u['max_m']]) for u in allu]):.0f}, max {max(u['max_m'] for u in allu)}",
          f"- Users with any negative savings/current balance: {sum(1 for u in allu if u['neg'])}",
          f"- UPI share of debits (median user): {statistics.median([u['upi_share'] for u in allu]):.0%}",
          f"- Share of UPI debits under ₹500: {sum(1 for u in allu for a in u['upi_amounts'] if a < 50000) / max(1, sum(len(u['upi_amounts']) for u in allu)):.0%}",
          f"- Dropped spends for insufficient funds: {sum(b.stats['insufficient_drop'] for b in eval_b):,}; top-ups injected: "
          f"{sum(b.stats['topup_self'] + b.stats['topup_family'] for b in eval_b):,}", ""]
    # planted
    L += ["## Planted answer key", "", "| Pattern | Planted (demo + eval) | Signal present in planted users | Accidental signals in non-planted users |", "| --- | --- | --- | --- |"]
    rows = T["planted_patterns"] + TE["planted_patterns"]
    neg = Counter()
    for b in demo_b + eval_b:
        neg += negative_checks(b)
    for ptype in ["forgotten_subscription", "price_hike", "category_creep", "duplicate_charge", "idle_cash", "expensive_card_balance"]:
        pr = [r for r in rows if r["pattern_type"] == ptype]
        if ptype == "category_creep":
            ok = sum(1 for r in pr if r["increase_pct"] and r["increase_pct"] >= 25)
        elif ptype == "idle_cash":
            ok = sum(1 for r in pr if r["flagged"] in (True, "true"))
        elif ptype == "expensive_card_balance":
            ok = sum(1 for r in pr if r["finance_charges_paise"] > 0)
        elif ptype == "duplicate_charge":
            ok = sum(1 for r in pr if r["both_posted"] in (True, "true"))
        elif ptype == "price_hike":
            ok = sum(1 for r in pr if r["first_new_charge_date"])
        else:
            ok = sum(1 for r in pr if r["mandate_txn_id"] and r["charges"] >= 3)
        L.append(f"| {ptype} | {len(pr)} | {ok} | {neg[ptype]} |")
    creeps = [r["increase_pct"] for r in rows if r["pattern_type"] == "category_creep" and r["increase_pct"] is not None]
    L += ["", f"Food-delivery creep measured on planted users: median +{statistics.median(creeps):.0f}% (min +{min(creeps)}%, max +{max(creeps)}%).", ""]
    # sms
    all_sms = [x for b in demo_b + eval_b for x in sms[b.s.user_id]]
    kinds = Counter(x["ground_truth"]["kind"] for x in all_sms)
    tpl = Counter(x["template_id"].split(".")[0] for x in all_sms)
    L += ["## Bank SMS", "", f"- SMS: {len(all_sms):,} ({kinds['debit']:,} debit, {kinds['credit']:,} credit, {kinds['ignore']:,} to ignore: OTPs, promos, statement notices)",
          f"- Held-out template variants (for parser evaluation): {sum(1 for x in all_sms if x['holdout']):,}",
          "- By bank: " + ", ".join(f"{k.upper()} {v:,}" for k, v in tpl.most_common()), ""]
    # groups
    ok_shares = all(sum(s["share_paise"] for s in e["shares"]) == e["amount_paise"] for g in gm.groups for e in g["expenses"])
    L += ["## Collab groups", "", f"- Groups: {len(gm.groups)} (" + ", ".join(f"{v} {k}" for k, v in sorted(Counter(g['type'] for g in gm.groups).items())) + ")",
          f"- Expenses: {sum(len(g['expenses']) for g in gm.groups):,}; settlements: {sum(len(g['settlements']) for g in gm.groups):,}",
          f"- Every expense's shares sum exactly to its amount: {'yes' if ok_shares else 'NO'}",
          "- Guest UPI IDs use the non-routable handle @pocketdemo", ""]
    L += integrity(demo_b + eval_b, T, TE, all_sms)
    return "\n".join(L)


def integrity(builders, T, TE, all_sms) -> list[str]:
    """Hard consistency checks a loader or parser would trip over. Every line should read 0 / yes."""
    txns = T["transactions"] + TE["transactions"]
    accts = {a["account_id"]: a for a in T["accounts"] + TE["accounts"]}
    by_id = {t["txn_id"]: t for t in txns}

    def dupes(vals):
        c = Counter(vals)
        return sum(v - 1 for v in c.values() if v > 1)

    # running balance in time order (ties keep posting order)
    chain_breaks, end_mismatch = 0, 0
    per_acc = defaultdict(list)
    for i, t in enumerate(txns):
        per_acc[t["account_id"]].append((t["occurred_at"], i, t))
    for aid, rows in per_acc.items():
        a = accts[aid]
        card = a["type"] == "credit_card"
        prev = a["opening_balance_paise"]
        for _, _, t in sorted(rows, key=lambda x: (x[0], x[1])):
            sign = 1 if (t["direction"] == "debit") == card else -1
            if t["balance_after_paise"] != prev + sign * t["amount_paise"]:
                chain_breaks += 1
            prev = t["balance_after_paise"]
        if prev != a["current_balance_paise"]:
            end_mismatch += 1
    # links
    sms_ids = {x["sms_id"] for x in all_sms}
    bad_sms_link = sum(1 for x in all_sms if x["transaction_id"] and x["transaction_id"] not in by_id)
    bad_txn_sms = sum(1 for t in txns if t["sms_ids"] and any(s not in sms_ids for s in t["sms_ids"].split("|")))
    bad_pair = 0
    for t in txns:
        q = t["transfer_pair_id"]
        if q:
            o = by_id.get(q)
            if not o or o["transfer_pair_id"] != t["txn_id"] or o["amount_paise"] != t["amount_paise"] or o["direction"] == t["direction"]:
                bad_pair += 1
    bad_rev = sum(1 for t in txns if t["reversal_of_id"] and (t["reversal_of_id"] not in by_id
                                                               or by_id[t["reversal_of_id"]]["amount_paise"] != t["amount_paise"]
                                                               or by_id[t["reversal_of_id"]]["status"] != "reversed"))
    bad_ref = sum(1 for t in txns if t["refund_of_id"] and (t["refund_of_id"] not in by_id
                                                             or by_id[t["refund_of_id"]]["amount_paise"] < t["amount_paise"]))
    ge = {e["expense_id"]: e for e in T["group_expenses"] + TE["group_expenses"]}
    bad_ge = sum(1 for e in ge.values() if e["linked_transaction_id"] and (e["linked_transaction_id"] not in by_id
                                                                            or by_id[e["linked_transaction_id"]]["amount_paise"] != e["amount_paise"]))
    # card statements: billed finance charges + charges after the last statement == all finance-charge txns
    fc_bad = 0
    sts = defaultdict(list)
    for st in T["card_statements"] + TE["card_statements"]:
        sts[st["account_id"]].append(st)
    for aid, L2 in sts.items():
        last = max(st["statement_date"] for st in L2)
        posted = sum(t["amount_paise"] for t in txns if t["account_id"] == aid and t["kind"] in ("fin_charge", "fin_charge_gst"))
        after = sum(t["amount_paise"] for t in txns if t["account_id"] == aid and t["kind"] in ("fin_charge", "fin_charge_gst")
                    and t["value_date"] > last)
        if sum(st["finance_charges_paise"] for st in L2) + after != posted:
            fc_bad += 1
    aligned = sum(b.stats["ts_aligned"] for b in builders)
    yes = lambda n: "0" if n == 0 else f"**{n}**"
    return ["## Integrity checks", "",
            "| Check | Result |", "| --- | --- |",
            f"| Duplicate txn_id / sms_id / account_id | {yes(dupes([t['txn_id'] for t in txns]))} / {yes(dupes([x['sms_id'] for x in all_sms]))} / {yes(dupes([a['account_id'] for a in T['accounts'] + TE['accounts']]))} |",
            f"| Running-balance breaks when rows are read in time order | {yes(chain_breaks)} of {len(txns):,} |",
            f"| Accounts whose last balance_after ≠ current_balance | {yes(end_mismatch)} of {len(accts):,} |",
            f"| SMS pointing at a missing transaction / txns pointing at a missing SMS | {yes(bad_sms_link)} / {yes(bad_txn_sms)} |",
            f"| Broken transfer pairs (missing, one-sided, amount or direction mismatch) | {yes(bad_pair)} |",
            f"| Reversals not matching a reversed original / refunds larger than the original | {yes(bad_rev)} / {yes(bad_ref)} |",
            f"| Group expenses linked to a missing or different-amount transaction | {yes(bad_ge)} |",
            f"| Cards whose statement finance charges don't reconcile with posted charges | {yes(fc_bad)} of {len(sts)} |",
            f"| Transactions re-timed to keep an account's statement in time order | {aligned} |", ""]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    a = ap.parse_args()
    print(run(Path(a.out)))


if __name__ == "__main__":
    main()
