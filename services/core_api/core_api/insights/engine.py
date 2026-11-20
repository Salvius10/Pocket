"""Insight engine: patterns found by code. Titles and bodies come from templates, never an LLM.

The six planted types follow the dataset's scoring rules exactly (data/README.md §6) and read
only what a bank feed would show: amounts, dates, accounts, balances, resolved merchant/category.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from pocket_common.money import div_half_up, money, pct_half_up
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api import models as m
from core_api.i18n import category_name, date_label, t
from core_api.ledger import mathx, summary
from core_api.ledger.context import Ctx

PLANTED_TYPES = ("forgotten_subscription", "price_hike", "category_creep", "duplicate_charge", "idle_cash", "expensive_card_balance")
CREEP_CATEGORY = "food_delivery"
RS = 100


@dataclass
class Found:
    type: str
    fingerprint: str
    severity: int
    impact_paise: int
    data: dict[str, Any] = field(default_factory=dict)
    proposal: dict[str, Any] | None = None


def _ok_debits(ctx: Ctx) -> list[m.Transaction]:
    return [x for x in ctx.txns if x.direction == "debit" and x.status == "success" and not x.hidden and x.reversal_of_id is None]


# ---------- the six planted types ----------
def forgotten_subscription(ctx: Ctx) -> list[Found]:
    by_merchant: dict[str, list[m.Transaction]] = defaultdict(list)
    for x in _ok_debits(ctx):
        if x.merchant and x.category == "subscriptions":
            by_merchant[x.merchant].append(x)
    out = []
    for merchant, rows in by_merchant.items():
        mandate = next((x for x in rows if x.amount_paise <= 5 * RS), None)
        if mandate is None:
            continue
        charges = [x for x in rows if x.occurred_at > mandate.occurred_at and x.amount_paise > 5 * RS]
        if len(charges) < 3:
            continue
        total = sum(x.amount_paise for x in charges)
        out.append(Found(
            "forgotten_subscription", f"forgotten_sub:{merchant}", 2, total,
            {"merchant": merchant, "name": charges[-1].merchant_name, "monthly_paise": charges[-1].amount_paise,
             "count": len(charges), "total_paise": total, "since": mandate.local_date.isoformat()},
        ))
    return out


def price_hike(ctx: Ctx) -> list[Found]:
    """A fixed-price bill that stepped up: the latest charge (within 45 days) is >=10% and >=Rs 20
    above the median of the 3 before it. Read from the feed alone, "fixed price" means the three
    charges before the step were the same amount, which is what rules out variable bills
    (electricity, gas) and everyday shops where every basket differs."""
    by_merchant: dict[str, list[m.Transaction]] = defaultdict(list)
    for x in _ok_debits(ctx):
        if x.merchant and x.amount_paise > 5 * RS and x.spend_class in ("flexible", "committed"):
            by_merchant[x.merchant].append(x)
    out = []
    for merchant, rows in by_merchant.items():
        if len(rows) < 4:
            continue
        latest = rows[-1]
        if (ctx.today - latest.local_date).days > 45:
            continue
        base = mathx.median_int([x.amount_paise for x in rows[-4:-1]])
        if not (latest.amount_paise * 10 >= base * 11 and latest.amount_paise - base >= 20 * RS):
            continue
        run = 1  # charges already made at the new price
        while run < len(rows) and rows[-1 - run].amount_paise == latest.amount_paise:
            run += 1
        before = rows[-run - 3 : -run]
        if len(before) < 3 or any(abs(x.amount_paise - base) * 50 > base for x in before):
            continue
        out.append(Found(
            "price_hike", f"price_hike:{merchant}:{latest.amount_paise}", 1, (latest.amount_paise - base) * 12,
            {"merchant": merchant, "name": latest.merchant_name, "old_paise": base, "new_paise": latest.amount_paise,
             "pct": pct_half_up(latest.amount_paise - base, base), "since": rows[-run].local_date.isoformat()},
        ))
    return out


def category_creep(ctx: Ctx) -> list[Found]:
    months = [mathx.shift_month_key(ctx.month, -i) for i in range(1, 7)]  # newest complete month first
    totals = [max(0, sum(e.paise for e in ctx.expenses if e.month == k and e.category == CREEP_CATEGORY)) for k in months]
    recent, earlier = totals[:3], totals[3:]
    recent_avg, earlier_avg = div_half_up(sum(recent), 3), div_half_up(sum(earlier), 3)
    if earlier_avg < 300 * RS or recent_avg * 100 < earlier_avg * 125:
        return []
    mtd = max(0, sum(e.paise for e in ctx.expenses if e.month == ctx.month and e.category == CREEP_CATEGORY))
    return [Found(
        "category_creep", f"creep:{CREEP_CATEGORY}:{ctx.month}", 2, recent_avg - earlier_avg,
        {"category": CREEP_CATEGORY, "recent_avg_paise": recent_avg, "earlier_avg_paise": earlier_avg,
         "pct": pct_half_up(recent_avg - earlier_avg, earlier_avg), "mtd_paise": mtd,
         "recent_months": months[:3], "earlier_months": months[3:]},
    )]


def duplicate_charge(ctx: Ctx) -> list[Found]:
    groups: dict[tuple[str, str, int], list[m.Transaction]] = defaultdict(list)
    for x in _ok_debits(ctx):
        who = x.merchant or (x.counterparty_name or "")
        if who and x.spend_class in ("flexible", "committed"):
            groups[(x.account_id, who, x.amount_paise)].append(x)
    out = []
    for rows in groups.values():
        for a, b in zip(rows, rows[1:], strict=False):
            if 0 <= (b.occurred_at - a.occurred_at).total_seconds() <= 600:
                recent = (ctx.today - b.local_date).days <= 30
                out.append(Found(
                    "duplicate_charge", f"dup:{b.id}", 3 if recent else 1, b.amount_paise,
                    {"merchant": b.merchant, "name": b.merchant_name, "amount_paise": b.amount_paise,
                     "date": b.local_date.isoformat(), "first_txn_id": a.id, "second_txn_id": b.id},
                ))
    return out


def _eod_min_balance(ctx: Ctx, account: m.Account, start: date, end: date) -> int | None:
    rows = [x for x in ctx.txns if x.account_id == account.id and x.balance_after_paise is not None]
    if not rows:
        return account.balance_paise
    balance: int | None = None
    idx = 0
    while idx < len(rows) and rows[idx].local_date < start:
        balance = rows[idx].balance_after_paise
        idx += 1
    lowest: int | None = None
    day = start
    while day <= end:
        while idx < len(rows) and rows[idx].local_date == day:
            balance = rows[idx].balance_after_paise
            idx += 1
        if balance is not None:
            lowest = balance if lowest is None else min(lowest, balance)
        day += timedelta(days=1)
    return lowest


def idle_cash(ctx: Ctx) -> list[Found]:
    out = []
    last_day = max((x.local_date for x in ctx.txns), default=ctx.today)
    end = min(last_day, ctx.today)
    start = end - timedelta(days=59)
    months = [mathx.shift_month_key(mathx.month_key(end), -i) for i in (1, 2, 3)]
    for a in ctx.accounts:
        if a.type not in ("savings", "current"):
            continue
        lowest = _eod_min_balance(ctx, a, start, end)
        if lowest is None:
            continue
        outflow = sum(
            x.amount_paise for x in ctx.txns
            if x.account_id == a.id and x.direction == "debit" and x.status == "success"
            and mathx.month_key(x.local_date) in months
        )
        avg_outflow = div_half_up(outflow, 3)
        idle = ((lowest - div_half_up(avg_outflow * 3, 2)) // (1000 * RS)) * (1000 * RS)
        if idle >= max(25_000 * RS, div_half_up(avg_outflow, 2)):
            out.append(Found(
                "idle_cash", f"idle:{a.id}:{mathx.month_key(end)}", 1, idle,
                {"account_id": a.id, "bank": a.institution_code or a.institution, "acct": a.masked_number[-4:],
                 "idle_paise": idle, "min_balance_paise": lowest, "avg_outflow_paise": avg_outflow},
            ))
    return out


def expensive_card_balance(ctx: Ctx) -> list[Found]:
    out = []
    last_day = max((x.local_date for x in ctx.txns), default=ctx.today)
    for a in ctx.accounts:
        if a.type != "credit_card":
            continue
        charges = [x for x in _ok_debits(ctx) if x.account_id == a.id and x.category == "card_interest"]
        if not charges:
            continue
        total = sum(x.amount_paise for x in charges)
        out.append(Found(
            "expensive_card_balance", f"card_revolve:{a.id}:{mathx.month_key(min(last_day, ctx.today))}", 3, total,
            {"account_id": a.id, "bank": a.institution_code or a.institution, "acct": a.masked_number[-4:],
             "charges_paise": total, "owed_paise": a.balance_paise, "rate_bps": a.interest_rate_bps,
             "next_month_cost_paise": mathx.monthly_interest_paise(a.balance_paise, a.interest_rate_bps or 0)},
        ))
    return out


# ---------- the rest ----------
def overspend_pocket(ctx: Ctx) -> list[Found]:
    out = []
    days_left = mathx.days_left_incl_today(ctx.today)
    for p in summary.pockets(ctx):
        if p["status"] == "over":
            out.append(Found("overspend_pocket", f"overspend:{p['id']}:{ctx.month}", 3, p["spent"]["paise"] - p["limit"]["paise"],
                             {"pocket_id": p["id"], "name": p["name"], "spent_paise": p["spent"]["paise"],
                              "limit_paise": p["limit"]["paise"], "days": days_left, "variant": "over"}))
        elif p["status"] == "watch" and ctx.today.day >= 7 and p["projected"]["paise"] * 10 > p["limit"]["paise"] * 11:
            out.append(Found("overspend_pocket", f"at_risk:{p['id']}:{ctx.month}", 2, p["projected"]["paise"] - p["limit"]["paise"],
                             {"pocket_id": p["id"], "name": p["name"], "projected_paise": p["projected"]["paise"],
                              "limit_paise": p["limit"]["paise"], "variant": "at_risk"}))
    return out


def spike(ctx: Ctx, skip: set[str]) -> list[Found]:
    out = []
    now = summary.category_totals(ctx, ctx.month)
    history = [summary.category_totals(ctx, mathx.shift_month_key(ctx.month, -i)) for i in (1, 2, 3)]
    for cid, amt in now.items():
        cat = ctx.categories.get(cid)
        if cat is None or cat.default_class != "flexible" or cid in skip or cid.startswith("business"):
            continue
        usual = mathx.median_int([h.get(cid, 0) for h in history])
        if usual >= 500 * RS and amt * 2 >= usual * 3 and amt - usual >= 1000 * RS:
            out.append(Found("spike", f"spike:{cid}:{ctx.month}", 2, amt - usual,
                             {"category": cid, "now_paise": amt, "usual_paise": usual}))
    return out


def subscription_overlap(ctx: Ctx, merchants: dict[str, m.Merchant]) -> list[Found]:
    by_sub: dict[str, list[m.RecurringItem]] = defaultdict(list)
    for r in ctx.recurring:
        mer = merchants.get(r.merchant or "")
        if r.kind == "subscription" and r.status == "active" and mer is not None and mer.subcategory:
            by_sub[mer.subcategory].append(r)
    out = []
    for sub, items in by_sub.items():
        if len(items) >= 2:
            total = sum(i.amount_paise for i in items)
            out.append(Found("subscription_overlap", f"overlap:{sub}", 1, total,
                             {"subcategory": sub, "count": len(items), "names": [i.name for i in items], "total_paise": total}))
    return out


def typical_income(ctx: Ctx) -> int:
    history = [summary.income_in_month(ctx, mathx.shift_month_key(ctx.month, -i)) for i in (1, 2, 3)]
    history = [h for h in history if h > 0]
    return mathx.median_int(history) if history else 0


def emi_load(ctx: Ctx) -> list[Found]:
    emi = sum(r.amount_paise for r in ctx.recurring if r.kind == "emi" and r.status == "active")
    income = typical_income(ctx)
    if emi == 0 or income == 0:
        return []
    pct = pct_half_up(emi, income)
    if pct < 40:
        return []
    return [Found("emi_load", f"emi_load:{ctx.month}", 3 if pct >= 50 else 2, emi,
                  {"emi_paise": emi, "income_paise": income, "pct": pct})]


def _surplus_candidates(ctx: Ctx) -> list[dict[str, Any]]:
    out = []
    for p in summary.pockets(ctx):
        surplus = p["limit"]["paise"] - p["projected"]["paise"]
        if p["status"] == "ok" and surplus >= 500 * RS:
            out.append({**p, "surplus_paise": surplus})
    return sorted(out, key=lambda p: -p["surplus_paise"])


def _top_goal(ctx: Ctx) -> dict[str, Any] | None:
    live = [g for g in summary.goals(ctx) if g["status"] != "reached"]
    return max(live, key=lambda g: (g["deadline"] is not None, g["priority"], g["target"]["paise"]), default=None)


def _move_proposal(pocket: dict[str, Any], goal: dict[str, Any], cap_paise: int) -> dict[str, Any]:
    amount = min(cap_paise, (pocket["surplus_paise"] // (500 * RS)) * (500 * RS), goal["left"]["paise"])
    return {"kind": "move_between_pockets",
            "payload": {"from_pocket_id": pocket["id"], "to_goal_id": goal["id"], "amount_paise": amount}}


def moved_this_month(ctx: Ctx) -> bool:
    """True once the user has accepted a suggested move this month. One nudge to move money is
    helpful; offering another the moment they accept is pushing."""
    return any(c.proposal_id and c.month == ctx.month for c in ctx.contributions) or any(
        a.proposal_id and a.month == ctx.month for a in ctx.adjustments
    )


def pocket_surplus(ctx: Ctx) -> list[Found]:
    if ctx.today.day < 12 or moved_this_month(ctx):
        return []
    goal = _top_goal(ctx)
    cands = _surplus_candidates(ctx)
    if goal is None or not cands:
        return []
    p = cands[0]
    prop = _move_proposal(p, goal, 5000 * RS)
    if prop["payload"]["amount_paise"] < 500 * RS:
        return []
    return [Found("pocket_surplus", f"surplus:{p['id']}:{ctx.month}", 1, prop["payload"]["amount_paise"],
                  {"pocket_id": p["id"], "name": p["name"], "surplus_paise": prop["payload"]["amount_paise"],
                   "goal_id": goal["id"], "goal": goal["name"]}, proposal=prop)]


def goal_off_track(ctx: Ctx) -> list[Found]:
    """Only the most important goal that is behind: one clear message beats a list of them."""
    behind = [g for g in summary.goals(ctx) if g["status"] == "behind"]
    if not behind:
        return []
    g = max(behind, key=lambda g: (g["priority"], g["monthly_need"]["paise"]))
    return [Found("goal_off_track", f"goal_behind:{g['id']}", 2, g["monthly_need"]["paise"] - g["monthly_plan"]["paise"],
                  {"goal_id": g["id"], "name": g["name"], "saved_paise": g["saved"]["paise"],
                   "target_paise": g["target"]["paise"], "need_paise": g["monthly_need"]["paise"]})]


def income_drop(ctx: Ctx) -> list[Found]:
    if (ctx.user.income_pattern or "") not in summary.VARIABLE_INCOME or ctx.today.day < 7:
        return []

    def to_day(key: str) -> int:
        ms = mathx.month_start(key)
        cutoff = ms.replace(day=min(ctx.today.day, mathx.days_in_month(ms)))
        return sum(x.amount_paise for x in ctx.txns if x.spend_class == "income" and x.direction == "credit"
                   and x.budget_month == key and x.local_date <= cutoff)

    now = to_day(ctx.month)
    past = [to_day(mathx.shift_month_key(ctx.month, -i)) for i in (1, 2, 3)]
    past = [p for p in past if p > 0]
    if not past:
        return []
    usual = div_half_up(sum(past), len(past))
    if now * 10 >= usual * 7:
        return []
    return [Found("income_drop", f"income_drop:{ctx.month}", 3, usual - now, {"now_paise": now, "usual_paise": usual})]


def detect_all(ctx: Ctx, merchants: dict[str, m.Merchant] | None = None) -> list[Found]:
    found: list[Found] = []
    creep = category_creep(ctx)
    found += forgotten_subscription(ctx) + price_hike(ctx) + creep + duplicate_charge(ctx) + idle_cash(ctx)
    found += expensive_card_balance(ctx) + overspend_pocket(ctx)
    found += spike(ctx, {c.data["category"] for c in creep}) + subscription_overlap(ctx, merchants or {})
    found += emi_load(ctx) + pocket_surplus(ctx) + goal_off_track(ctx) + income_drop(ctx)
    # The creep insight carries the "move the spare money to your goal" suggestion when there is one.
    goal = _top_goal(ctx)
    cands = [p for p in _surplus_candidates(ctx) if CREEP_CATEGORY not in p["category_ids"]]
    for f in creep:
        if goal is not None and cands and not moved_this_month(ctx):
            prop = _move_proposal(cands[0], goal, 3000 * RS)
            if prop["payload"]["amount_paise"] >= 500 * RS:
                f.proposal = prop
                f.data["suggest_from"] = cands[0]["name"]
                f.data["suggest_goal"] = goal["name"]
    # One suggestion per pocket: if the creep insight already offers the move, drop the plain surplus one.
    offered = {f.proposal["payload"]["from_pocket_id"] for f in creep if f.proposal}
    found = [f for f in found if not (f.type == "pocket_surplus" and f.data.get("pocket_id") in offered)]
    return sorted(found, key=lambda f: (-f.severity, -f.impact_paise, f.fingerprint))


# ---------- words ----------
def render(ctx: Ctx, type_: str, data: dict[str, Any]) -> dict[str, str]:
    """Title/body for the screen (display amounts) and a `say` line for the mascot (spoken amounts)."""

    def both(paise: int) -> tuple[str, str]:
        mm = money(int(paise), ctx.lang)
        return mm["display"], mm["spoken"]

    def cat(cid: str) -> str:
        c = ctx.categories.get(cid)
        return category_name(c, ctx.lang) if c else cid

    key = type_
    args_d: dict[str, Any] = {}
    args_s: dict[str, Any] = {}

    def put(name: str, paise: int) -> None:
        args_d[name], args_s[name] = both(paise)

    def same(**kw: Any) -> None:
        args_d.update(kw)
        args_s.update(kw)

    if type_ == "overspend_pocket":
        same(name=data.get("name", ""), days=data.get("days", 0))
        put("limit", data.get("limit_paise", 0))
        if data.get("variant") == "at_risk":
            key = "pocket_at_risk"
            put("projected", data.get("projected_paise", 0))
        else:
            put("spent", data.get("spent_paise", 0))
    elif type_ == "category_creep":
        same(name=cat(data["category"]), pct=data["pct"])
        put("recent", data["recent_avg_paise"])
        put("earlier", data["earlier_avg_paise"])
        put("mtd", data["mtd_paise"])
    elif type_ == "spike":
        same(name=cat(data["category"]))
        put("now", data["now_paise"])
        put("usual", data["usual_paise"])
    elif type_ == "forgotten_subscription":
        same(name=data["name"], count=data["count"])
        put("monthly", data["monthly_paise"])
        put("total", data["total_paise"])
    elif type_ == "subscription_overlap":
        same(count=data["count"], names=", ".join(data["names"]))
        put("total", data["total_paise"])
    elif type_ == "price_hike":
        same(name=data["name"], pct=data["pct"])
        put("old", data["old_paise"])
        put("new", data["new_paise"])
    elif type_ == "duplicate_charge":
        same(name=data["name"], date=date_label(ctx.lang, date.fromisoformat(data["date"])))
        put("amt", data["amount_paise"])
    elif type_ == "idle_cash":
        same(bank=data["bank"], acct=data["acct"])
        put("amt", data["idle_paise"])
        put("min", data["min_balance_paise"])
    elif type_ == "expensive_card_balance":
        same(bank=data["bank"], acct=data["acct"])
        put("charges", data["charges_paise"])
        put("owed", data["owed_paise"])
    elif type_ == "emi_load":
        same(pct=data["pct"])
        put("emi", data["emi_paise"])
        put("income", data["income_paise"])
    elif type_ == "pocket_surplus":
        same(name=data["name"], goal=data["goal"])
        put("surplus", data["surplus_paise"])
    elif type_ == "goal_off_track":
        same(name=data["name"])
        put("saved", data["saved_paise"])
        put("target", data["target_paise"])
        put("need", data["need_paise"])
    elif type_ == "income_drop":
        put("now", data["now_paise"])
        put("usual", data["usual_paise"])
    title = t(ctx.lang, f"insight.{key}.title", **args_d)
    body = t(ctx.lang, f"insight.{key}.body", **args_d)
    say = t(ctx.lang, f"insight.{key}.title", **args_s) + ". " + t(ctx.lang, f"insight.{key}.body", **args_s)
    return {"title": title, "body": body, "say": say}


# ---------- persistence ----------
async def load_merchants(session: AsyncSession) -> dict[str, m.Merchant]:
    from core_api.ledger.context import _ref_cache

    if "merchants" not in _ref_cache:
        _ref_cache["merchants"] = {x.key: x for x in (await session.execute(select(m.Merchant))).scalars()}
    return _ref_cache["merchants"]  # type: ignore[no-any-return]


async def run_insights(session: AsyncSession, ctx: Ctx) -> list[m.Insight]:
    """Detect, then upsert by fingerprint. A dismissed insight stays dismissed."""
    from core_api.proposals.service import create_proposal

    found = detect_all(ctx, await load_merchants(session))
    existing = {i.fingerprint: i for i in (await session.execute(select(m.Insight).where(m.Insight.user_id == ctx.user.id))).scalars()}
    seen: set[str] = set()
    for f in found:
        seen.add(f.fingerprint)
        row = existing.get(f.fingerprint)
        if row is None:
            row = m.Insight(user_id=ctx.user.id, type=f.type, fingerprint=f.fingerprint, status="active")
            session.add(row)
            existing[f.fingerprint] = row
        row.severity, row.impact_paise, row.data = f.severity, f.impact_paise, f.data
        if row.status == "resolved":
            row.status = "active"
        if f.proposal is not None and row.status == "active":
            prop = await session.get(m.Proposal, row.proposal_id) if row.proposal_id else None
            if prop is None or prop.status in ("declined", "expired") and prop.payload != f.proposal["payload"]:
                await session.flush()
                prop = await create_proposal(session, ctx, f.proposal["kind"], f.proposal["payload"], source="insight", insight_id=row.id)
                row.proposal_id = prop.id
            elif prop.status == "pending" and prop.payload != f.proposal["payload"]:
                prop.status = "expired"
                await session.flush()
                new = await create_proposal(session, ctx, f.proposal["kind"], f.proposal["payload"], source="insight", insight_id=row.id)
                row.proposal_id = new.id
    for fp, row in existing.items():
        if fp not in seen and row.status == "active":
            row.status = "resolved"
    await session.flush()
    return [existing[f.fingerprint] for f in found]


async def list_insights(session: AsyncSession, ctx: Ctx, limit: int = 20) -> list[dict[str, Any]]:
    rows = list((await session.execute(
        select(m.Insight).where(m.Insight.user_id == ctx.user.id, m.Insight.status == "active")
        .order_by(m.Insight.severity.desc(), m.Insight.impact_paise.desc(), m.Insight.fingerprint)
    )).scalars())
    out = []
    for row in rows[:limit]:
        words = render(ctx, row.type, row.data)
        proposal = None
        if row.proposal_id:
            from core_api.proposals.service import proposal_view

            p = await session.get(m.Proposal, row.proposal_id)
            if p is not None and p.status == "pending":
                proposal = proposal_view(ctx, p)
        out.append({"id": row.id, "type": row.type, "severity": row.severity, "impact": dict(money(row.impact_paise, ctx.lang)),
                    **words, "proposal": proposal, "created_at": row.created_at.isoformat() if row.created_at else None})
    return out
