"""Every number the app shows. The phone and the mascot both read from here and nowhere else."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pocket_common.money import div_half_up, money, pct_half_up

from core_api.config import get_settings
from core_api.i18n import category_name, date_label, month_label, t
from core_api.ledger import mathx
from core_api.ledger.context import Ctx

SECTIONS = ("safe_to_spend", "pockets", "goals", "spend_by_category", "cash_flow", "bills", "net_worth", "investments")
DUE_KINDS = ("rent", "emi", "bill", "subscription", "insurance", "sip")
MAIN_INCOME = ("salary", "allowance")
VARIABLE_INCOME = ("gig", "business")


def M(ctx: Ctx, paise: int) -> dict[str, Any]:
    return dict(money(paise, ctx.lang))


def _to_paise(d: Decimal) -> int:
    return int(d.quantize(Decimal(1), rounding=ROUND_HALF_UP))


# ---------- building blocks ----------
def income_in_month(ctx: Ctx, month: str, categories: tuple[str, ...] | None = None) -> int:
    return sum(
        x.amount_paise
        for x in ctx.txns
        if x.budget_month == month and x.spend_class == "income" and x.direction == "credit"
        and (categories is None or x.category in categories)
    )


def expense_in_month(ctx: Ctx, month: str, spend_class: str | None = None) -> int:
    return sum(e.paise for e in ctx.expenses if e.month == month and (spend_class is None or e.spend_class == spend_class))


def category_totals(ctx: Ctx, month: str) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for e in ctx.expenses:
        if e.month == month and e.category != "refund":
            out[e.category] += e.paise
    return {k: v for k, v in out.items() if v > 0}


def expected_income(ctx: Ctx) -> int:
    """Income still to come this month (ARCHITECTURE.md §6)."""
    pattern = ctx.user.income_pattern or "salaried"
    days_left = mathx.days_left_incl_today(ctx.today)
    if pattern in VARIABLE_INCOME:
        start = ctx.today - timedelta(days=30)
        last30 = sum(
            x.amount_paise for x in ctx.txns
            if x.spend_class == "income" and x.direction == "credit" and start <= x.local_date < ctx.today
        )
        # 0.8 x average daily income of the last 30 days x days left
        return last30 * 8 * days_left // (30 * 10)
    received = income_in_month(ctx, ctx.month, MAIN_INCOME)
    history = [income_in_month(ctx, mathx.shift_month_key(ctx.month, -i), MAIN_INCOME) for i in (1, 2, 3)]
    history = [h for h in history if h > 0]
    if not history:
        return 0
    typical = mathx.median_int(history)
    return typical - received if received * 2 < typical else 0


def due_items(ctx: Ctx, start: date, end: date) -> list[dict[str, Any]]:
    """Recurring payments expected between two dates (inclusive), soonest first."""
    out: list[dict[str, Any]] = []
    for r in ctx.recurring:
        nd = ctx.next_due.get(r.id)
        if r.kind not in DUE_KINDS or nd is None or not start <= nd <= end:
            continue
        out.append(
            {"id": r.id, "name": r.name, "kind": r.kind, "amount_paise": r.amount_paise, "due_date": nd,
             "autopay": (r.channel or "") in ("ach", "autopay", "card"), "variable": r.amount_is_variable,
             "category": r.category}
        )
    return sorted(out, key=lambda d: (d["due_date"], d["name"]))


def goal_saved(ctx: Ctx, goal_id: str) -> int:
    return sum(c.amount_paise for c in ctx.contributions if c.goal_id == goal_id)


def goal_monthly_need(ctx: Ctx, goal: Any) -> int:
    remaining = max(0, int(goal.target_paise) - goal_saved(ctx, goal.id))
    if remaining == 0 or goal.status != "active":
        return 0
    if goal.monthly_plan_paise:
        return min(int(goal.monthly_plan_paise), remaining)
    if goal.deadline is not None:
        if goal.deadline < ctx.today:
            return remaining
        months = mathx.months_between(ctx.today, goal.deadline)
        return -(-remaining // months)  # ceil: never plan to fall short
    return 0


def goal_usual_monthly(ctx: Ctx, goal_id: str) -> int:
    """What the user normally sets aside for this goal: the median of the last 3 earlier months."""
    by_month: dict[str, int] = defaultdict(int)
    for c in ctx.contributions:
        if c.goal_id == goal_id and c.month < ctx.month and (c.note or "") != "Already saved at setup":
            by_month[c.month] += c.amount_paise
    recent = [by_month[k] for k in sorted(by_month)[-3:]]
    return mathx.median_int(recent) if recent else 0


def goal_plan(ctx: Ctx, goal: Any) -> int:
    """The monthly amount the goal is being funded at: the stated plan, else the usual amount,
    else (a brand-new goal with a deadline) what the deadline needs."""
    if goal.monthly_plan_paise:
        return int(goal.monthly_plan_paise)
    usual = goal_usual_monthly(ctx, goal.id)
    if usual:
        return usual
    return goal_monthly_need(ctx, goal)


def goal_reserve(ctx: Ctx) -> int:
    """What goals need this month, or what was already put in if that is more."""
    total = 0
    for g in ctx.goals:
        if g.status != "active":
            continue
        put_in = sum(c.amount_paise for c in ctx.contributions if c.goal_id == g.id and c.month == ctx.month)
        remaining_before = max(0, g.target_paise - (goal_saved(ctx, g.id) - put_in))
        total += max(min(goal_plan(ctx, g), remaining_before), put_in)
    return total


def sts_calc(ctx: Ctx) -> mathx.SafeToSpend:
    cached = ctx.memo.get("sts")
    if cached is not None:
        return cached  # type: ignore[no-any-return]
    income = income_in_month(ctx, ctx.month) + expected_income(ctx)
    sip_paid = sum(
        x.amount_paise for x in ctx.txns
        if x.budget_month == ctx.month and x.spend_class == "saving" and x.direction == "debit" and x.recurring_item_id
    )
    start = date(ctx.today.year, ctx.today.month, 1)
    still_due = sum(d["amount_paise"] for d in due_items(ctx, start, mathx.month_end(ctx.today)))
    committed = expense_in_month(ctx, ctx.month, "committed") + sip_paid + still_due
    flex_before = sum(e.paise for e in ctx.expenses if e.month == ctx.month and e.spend_class == "flexible" and e.day < ctx.today)
    flex_today = sum(e.paise for e in ctx.expenses if e.month == ctx.month and e.spend_class == "flexible" and e.day == ctx.today)
    res = mathx.safe_to_spend(
        income, committed, goal_reserve(ctx), max(0, flex_before), max(0, flex_today), mathx.days_left_incl_today(ctx.today)
    )
    ctx.memo["sts"] = res
    return res


# ---------- sections ----------
def safe_to_spend(ctx: Ctx) -> dict[str, Any]:
    s = sts_calc(ctx)
    flexible_left = s.spendable_paise - s.flexible_before_today_paise - s.flexible_today_paise
    if s.daily_paise == 0:
        status, say = "empty", t(ctx.lang, "sts.say_zero")
    elif s.left_today_paise < 0:
        status = "over"
        say = t(ctx.lang, "sts.say_over", over=M(ctx, -s.left_today_paise)["spoken"], daily=M(ctx, s.daily_paise)["spoken"], days=s.days_left)
    else:
        status = "ok"
        say = t(ctx.lang, "sts.say", daily=M(ctx, s.daily_paise)["spoken"], days=s.days_left, left=M(ctx, s.left_today_paise)["spoken"])
    return {
        "daily": M(ctx, s.daily_paise), "left_today": M(ctx, s.left_today_paise), "spent_today": M(ctx, s.flexible_today_paise),
        "days_left": s.days_left, "day_of_month": ctx.today.day, "days_in_month": mathx.days_in_month(ctx.today),
        "income": M(ctx, s.income_paise), "committed": M(ctx, s.committed_paise), "goal_reserve": M(ctx, s.goal_reserve_paise),
        "spendable": M(ctx, s.spendable_paise), "flexible_spent": M(ctx, s.flexible_before_today_paise + s.flexible_today_paise),
        "flexible_left": M(ctx, flexible_left), "status": status, "say": say,
    }


def pocket_limit(ctx: Ctx, pocket: Any, month: str | None = None) -> int:
    month = month or ctx.month
    return int(pocket.monthly_limit_paise) + sum(a.delta_paise for a in ctx.adjustments if a.pocket_id == pocket.id and a.month == month)


def pocket_spent(ctx: Ctx, pocket: Any, month: str | None = None) -> int:
    month = month or ctx.month
    cats = set(pocket.category_ids or [])
    return max(0, sum(e.paise for e in ctx.expenses if e.month == month and e.category in cats))


def pockets(ctx: Ctx) -> list[dict[str, Any]]:
    dim, dom = mathx.days_in_month(ctx.today), ctx.today.day
    out = []
    for p in ctx.pockets:
        if p.status == "archived":
            continue
        limit, spent = pocket_limit(ctx, p), pocket_spent(ctx, p)
        projected = div_half_up(spent * dim, dom)
        status = "paused" if p.status == "paused" else "over" if spent > limit else "watch" if projected > limit else "ok"
        say = (
            t(ctx.lang, "pocket.say_over", name=p.name, over=M(ctx, spent - limit)["spoken"], spent=M(ctx, spent)["spoken"], limit=M(ctx, limit)["spoken"])
            if spent > limit
            else t(ctx.lang, "pocket.say", name=p.name, spent=M(ctx, spent)["spoken"], limit=M(ctx, limit)["spoken"])
        )
        out.append(
            {"id": p.id, "name": p.name, "emoji": p.emoji, "category_ids": list(p.category_ids or []),
             "limit": M(ctx, limit), "base_limit": M(ctx, int(p.monthly_limit_paise)), "spent": M(ctx, spent),
             "left": M(ctx, limit - spent), "pct": pct_half_up(spent, limit), "projected": M(ctx, projected),
             "status": status, "say": say}
        )
    return out


def goals(ctx: Ctx) -> list[dict[str, Any]]:
    out = []
    for g in ctx.goals:
        if g.status == "archived":
            continue
        saved = goal_saved(ctx, g.id)
        need = goal_monthly_need(ctx, g)
        this_month = sum(c.amount_paise for c in ctx.contributions if c.goal_id == g.id and c.month == ctx.month)
        if saved >= g.target_paise:
            status = "reached"
        elif g.deadline is not None and g.deadline < ctx.today:
            status = "behind"
        elif g.deadline is not None:
            months = mathx.months_between(ctx.today, g.deadline)
            status = "behind" if saved + goal_plan(ctx, g) * months < g.target_paise else "on_track"
        else:
            status = "on_track"
        say = t(ctx.lang, "goal.say", name=g.name, saved=M(ctx, saved)["spoken"], target=M(ctx, g.target_paise)["spoken"])
        if need and status != "reached":
            say += " " + t(ctx.lang, "goal.say_need", need=M(ctx, need)["spoken"])
        out.append(
            {"id": g.id, "name": g.name, "emoji": g.emoji, "target": M(ctx, g.target_paise), "saved": M(ctx, saved),
             "left": M(ctx, max(0, g.target_paise - saved)), "pct": min(100, pct_half_up(saved, g.target_paise)),
             "deadline": g.deadline.isoformat() if g.deadline else None,
             "deadline_label": date_label(ctx.lang, g.deadline) + f" {g.deadline.year}" if g.deadline else None,
             "monthly_need": M(ctx, need), "monthly_plan": M(ctx, goal_plan(ctx, g)), "this_month": M(ctx, this_month), "priority": g.priority, "status": status, "say": say}
        )
    return out


def _category_rows(ctx: Ctx, totals: dict[str, int]) -> list[dict[str, Any]]:
    total = sum(totals.values())
    rows = []
    for cid, amt in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0])):
        cat = ctx.categories.get(cid)
        rows.append(
            {"category_id": cid, "name": category_name(cat, ctx.lang) if cat else cid, "emoji": cat.emoji if cat else "",
             "amount": M(ctx, amt), "pct": pct_half_up(amt, total)}
        )
    return rows


def spend_by_category(ctx: Ctx) -> dict[str, Any]:
    this_t = category_totals(ctx, ctx.month)
    last_key = mathx.shift_month_key(ctx.month, -1)
    last_t = category_totals(ctx, last_key)
    rows = _category_rows(ctx, this_t)
    total = sum(this_t.values())
    say_parts = []
    if rows:
        say_parts.append(t(ctx.lang, "cat.say_top", a_name=rows[0]["name"], a_amt=rows[0]["amount"]["spoken"]))
    if len(rows) >= 3:
        say_parts.append(t(ctx.lang, "cat.say_next", b_name=rows[1]["name"], b_amt=rows[1]["amount"]["spoken"],
                           c_name=rows[2]["name"], c_amt=rows[2]["amount"]["spoken"]))
    say_parts.append(t(ctx.lang, "cat.say_total", total=M(ctx, total)["spoken"]))
    return {
        "month": ctx.month, "this_month": rows, "total": M(ctx, total),
        "last_month_key": last_key, "last_month": _category_rows(ctx, last_t), "last_total": M(ctx, sum(last_t.values())),
        "say": " ".join(say_parts),
    }


def cash_flow(ctx: Ctx) -> dict[str, Any]:
    months = []
    for i in range(11, -1, -1):
        key = mathx.shift_month_key(ctx.month, -i)
        inc, spend = income_in_month(ctx, key), max(0, expense_in_month(ctx, key))
        saved = sum(x.amount_paise for x in ctx.txns if x.budget_month == key and x.spend_class == "saving" and x.direction == "debit")
        ms = mathx.month_start(key)
        months.append({"month": key, "label": month_label(ctx.lang, ms.month), "income": M(ctx, inc), "spend": M(ctx, spend),
                       "saved": M(ctx, saved), "net": M(ctx, inc - spend - saved)})
    week_start = ctx.today - timedelta(days=ctx.today.weekday())
    weeks = []
    for i in range(7, -1, -1):
        ws = week_start - timedelta(days=7 * i)
        we = ws + timedelta(days=6)
        inc = sum(x.amount_paise for x in ctx.txns if x.spend_class == "income" and x.direction == "credit" and ws <= x.local_date <= we)
        spend = max(0, sum(e.paise for e in ctx.expenses if ws <= e.day <= we))
        weeks.append({"start": ws.isoformat(), "label": date_label(ctx.lang, ws), "income": M(ctx, inc), "spend": M(ctx, spend)})
    cur: dict[str, Any] = months[-1]
    return {"months": months, "weeks": weeks,
            "say": t(ctx.lang, "cash.say", income=cur["income"]["spoken"], spend=cur["spend"]["spoken"])}


def bills(ctx: Ctx, window_days: int = 30) -> dict[str, Any]:
    end = ctx.today + timedelta(days=window_days)
    items = due_items(ctx, ctx.today - timedelta(days=3), end)
    for st in ctx.statements:
        if st.paid_paise is None and ctx.today - timedelta(days=3) <= st.due_date <= end and st.total_due_paise > 0:
            acct = ctx.account(st.account_id)
            items.append(
                {"id": st.id, "name": t(ctx.lang, "label.card_bill", bank=(acct.institution_code or acct.institution) if acct else ""),
                 "kind": "card_bill", "amount_paise": st.total_due_paise, "min_due_paise": st.min_due_paise,
                 "due_date": st.due_date, "autopay": False, "variable": True, "category": "card_payment"}
            )
    items.sort(key=lambda d: (d["due_date"], d["name"]))
    rows = []
    for d in items:
        days = (d["due_date"] - ctx.today).days
        rows.append(
            {"id": d["id"], "name": d["name"], "kind": d["kind"], "amount": M(ctx, d["amount_paise"]),
             "min_due": M(ctx, d["min_due_paise"]) if d.get("min_due_paise") else None,
             "due_date": d["due_date"].isoformat(), "due_label": date_label(ctx.lang, d["due_date"]),
             "days_until": days, "autopay": d["autopay"], "variable": d["variable"], "category": d["category"]}
        )
    total = sum(d["amount_paise"] for d in items)
    if rows:
        say = t(ctx.lang, "bills.say", count=len(rows), days=window_days, total=M(ctx, total)["spoken"],
                name=rows[0]["name"], amt=rows[0]["amount"]["spoken"], date=rows[0]["due_label"])
    else:
        say = t(ctx.lang, "bills.say_none", days=window_days)
    emi_total = sum(r.amount_paise for r in ctx.recurring if r.kind == "emi" and r.status == "active")
    return {"window_days": window_days, "upcoming": rows, "total_due": M(ctx, total), "count": len(rows),
            "emi_monthly": M(ctx, emi_total), "say": say}


def _nav_on_or_before(series: list[tuple[date, Decimal]], day: date) -> Decimal | None:
    best: Decimal | None = None
    for d, v in series:
        if d <= day:
            best = v
        else:
            break
    return best


def investments(ctx: Ctx) -> dict[str, Any]:
    gold_price = get_settings().gold_price_per_gram_paise
    rows: list[dict[str, Any]] = []
    total = invested_total = week_total = mf_total = 0
    for h in ctx.holdings:
        value, invested, week, week_bps, detail = 0, int(h.invested_paise or 0), 0, None, ""
        if h.kind == "mutual_fund" and h.scheme_code and h.units is not None:
            series = ctx.nav.get(int(h.scheme_code), [])
            if series:
                latest_day, latest = series[-1]
                prev = _nav_on_or_before(series, latest_day - timedelta(days=7)) or latest
                value = _to_paise(Decimal(h.units) * latest * 100)
                week = _to_paise(Decimal(h.units) * (latest - prev) * 100)
                week_bps = int(((latest - prev) / prev * 10000).quantize(Decimal(1), rounding=ROUND_HALF_UP)) if prev else 0
                mf_total += value
                week_total += week
        elif h.kind == "fd":
            value = invested = int(h.fd_principal_paise or 0)
            detail = h.fd_maturity_date.isoformat() if h.fd_maturity_date else ""
        elif h.kind in ("ppf", "epf"):
            value = int(h.balance_paise or 0)
            invested = invested or value
        elif h.kind == "gold":
            grams = Decimal(h.gold_grams or 0)
            value = _to_paise(grams * gold_price) if gold_price else 0
            detail = f"{grams.normalize()} g"
        total += value
        invested_total += invested if h.kind != "gold" else 0
        rows.append(
            {"id": h.id, "kind": h.kind, "name": h.name, "value": M(ctx, value), "invested": M(ctx, invested),
             "gain": M(ctx, value - invested) if h.kind == "mutual_fund" else None,
             "week_change": M(ctx, week) if h.kind == "mutual_fund" else None, "week_change_bps": week_bps,
             "sip": M(ctx, int(h.sip_amount_paise)) if h.sip_amount_paise else None, "sip_day": h.sip_day,
             "detail": detail, "approx": h.kind == "gold"}
        )
    rows.sort(key=lambda r: -r["value"]["paise"])
    nifty = ctx.nav.get(get_settings().nifty_proxy_scheme_code, [])
    nifty_bps = None
    if nifty:
        d, latest = nifty[-1]
        prev = _nav_on_or_before(nifty, d - timedelta(days=7)) or latest
        nifty_bps = int(((latest - prev) / prev * 10000).quantize(Decimal(1), rounding=ROUND_HALF_UP)) if prev else 0
    if rows:
        say = t(ctx.lang, "inv.say", total=M(ctx, total)["spoken"], week=M(ctx, abs(week_total))["spoken"],
                dir=t(ctx.lang, "dir.up" if week_total >= 0 else "dir.down"))
    else:
        say = t(ctx.lang, "inv.say_none")
    return {"total": M(ctx, total), "invested": M(ctx, invested_total), "mutual_funds": M(ctx, mf_total),
            "week_change": M(ctx, week_total), "week_change_abs": M(ctx, abs(week_total)),
            "week_direction": "up" if week_total >= 0 else "down", "nifty_week_bps": nifty_bps,
            "nav_as_of": max((s[-1][0] for s in ctx.nav.values() if s), default=ctx.today).isoformat(),
            "holdings": rows, "say": say}


def net_worth(ctx: Ctx) -> dict[str, Any]:
    inv = investments(ctx)
    bank = sum(a.balance_paise for a in ctx.accounts if a.type in ("savings", "current", "wallet"))
    cards = sum(a.balance_paise for a in ctx.accounts if a.type == "credit_card")
    loans = sum(ln.outstanding_paise for ln in ctx.loans)
    by_kind: dict[str, int] = defaultdict(int)
    for h in inv["holdings"]:
        by_kind[h["kind"]] += h["value"]["paise"]
    breakdown = [
        ("bank_accounts", bank, "asset"), ("mutual_funds", by_kind["mutual_fund"], "asset"), ("fd", by_kind["fd"], "asset"),
        ("ppf_epf", by_kind["ppf"] + by_kind["epf"], "asset"), ("gold", by_kind["gold"], "asset"),
        ("cards", cards, "liability"), ("loans", loans, "liability"),
    ]
    assets = sum(v for _, v, side in breakdown if side == "asset")
    liab = cards + loans
    return {
        "total": M(ctx, assets - liab), "assets": M(ctx, assets), "liabilities": M(ctx, liab),
        "breakdown": [{"key": k, "label": t(ctx.lang, f"label.{k}"), "amount": M(ctx, v), "side": side}
                      for k, v, side in breakdown if v > 0],
        "say": t(ctx.lang, "networth.say", total=M(ctx, assets - liab)["spoken"], assets=M(ctx, assets)["spoken"], liab=M(ctx, liab)["spoken"]),
    }


_BUILDERS = {
    "safe_to_spend": safe_to_spend, "pockets": pockets, "goals": goals, "spend_by_category": spend_by_category,
    "cash_flow": cash_flow, "bills": bills, "net_worth": net_worth, "investments": investments,
}


def build_summary(ctx: Ctx, sections: list[str] | None = None) -> dict[str, Any]:
    wanted = [s for s in (sections or SECTIONS) if s in _BUILDERS]
    out: dict[str, Any] = {"today": ctx.today.isoformat(), "month": ctx.month, "lang": ctx.lang}
    for s in wanted:
        out[s] = _BUILDERS[s](ctx)
    return out


# ---------- tools that need a little more than a section ----------
def check_affordability(ctx: Ctx, amount_paise: int) -> dict[str, Any]:
    s = sts_calc(ctx)
    left_month = s.spendable_paise - s.flexible_before_today_paise - s.flexible_today_paise
    after = left_month - amount_paise
    fits_month = after >= 0
    fits_today = amount_paise <= s.left_today_paise
    days_after = max(1, s.days_left - 1)
    new_daily = (max(0, after) // days_after // mathx.TEN_RUPEES) * mathx.TEN_RUPEES
    amt = M(ctx, amount_paise)
    if not fits_month:
        say = t(ctx.lang, "afford.say_no", have=M(ctx, max(0, left_month))["spoken"], amount=amt["spoken"], short=M(ctx, -after)["spoken"])
    elif fits_today:
        say = t(ctx.lang, "afford.say_yes", amount=amt["spoken"], left=M(ctx, after)["spoken"], daily=M(ctx, new_daily)["spoken"])
    else:
        say = t(ctx.lang, "afford.say_today_no", left=M(ctx, after)["spoken"], daily=M(ctx, new_daily)["spoken"])
    return {"amount": amt, "fits_today": fits_today, "fits_month": fits_month, "flexible_left_now": M(ctx, left_month),
            "flexible_left_after": M(ctx, after), "new_daily": M(ctx, new_daily), "left_today": M(ctx, s.left_today_paise), "say": say}


def _period(ctx: Ctx, name: str) -> tuple[date, date]:
    today = ctx.today
    first = date(today.year, today.month, 1)
    if name in ("this_month", "month"):
        return first, today
    if name == "last_month":
        prev = mathx.add_months(first, -1)
        return prev, mathx.month_end(prev)
    if name == "last_month_to_date":
        prev = mathx.add_months(first, -1)
        return prev, prev.replace(day=min(today.day, mathx.days_in_month(prev)))
    if name == "this_week":
        ws = today - timedelta(days=today.weekday())
        return ws, today
    if name == "last_week":
        ws = today - timedelta(days=today.weekday() + 7)
        return ws, ws + timedelta(days=6)
    if name == "last_7_days":
        return today - timedelta(days=6), today
    if name == "last_30_days":
        return today - timedelta(days=29), today
    if name == "last_3_months":
        return mathx.add_months(first, -3), first - timedelta(days=1)
    if len(name) == 7 and name[4] == "-":
        ms = mathx.month_start(name)
        return ms, mathx.month_end(ms)
    return first, today


def spend_between(ctx: Ctx, start: date, end: date, category: str | None = None) -> int:
    return max(0, sum(e.paise for e in ctx.expenses if start <= e.day <= end and (category is None or e.category == category)))


def compare_spend(ctx: Ctx, category: str | None, period_a: str, period_b: str) -> dict[str, Any]:
    a0, a1 = _period(ctx, period_a)
    b0, b1 = _period(ctx, period_b)
    a, b = spend_between(ctx, a0, a1, category), spend_between(ctx, b0, b1, category)
    delta = b - a
    pct = pct_half_up(abs(delta), a) if a else 0
    cat = ctx.categories.get(category or "")
    what = category_name(cat, ctx.lang) if cat else t(ctx.lang, "spending")
    key = "compare.say_same" if delta == 0 else "compare.say_up" if delta > 0 else "compare.say_down"
    say = t(ctx.lang, key, what=what, a=M(ctx, a)["spoken"], b=M(ctx, b)["spoken"], delta=M(ctx, abs(delta))["spoken"], pct=pct)
    return {"category": category, "what": what, "period_a": {"name": period_a, "from": a0.isoformat(), "to": a1.isoformat(), "total": M(ctx, a)},
            "period_b": {"name": period_b, "from": b0.isoformat(), "to": b1.isoformat(), "total": M(ctx, b)},
            "delta": M(ctx, delta), "delta_abs": M(ctx, abs(delta)), "delta_pct": pct,
            "direction": "same" if delta == 0 else "up" if delta > 0 else "down", "say": say}


def txn_row(ctx: Ctx, x: Any) -> dict[str, Any]:
    cat = ctx.categories.get(x.category)
    acct = ctx.account(x.account_id)
    return {
        "id": x.id, "occurred_at": x.occurred_at.isoformat(), "date": x.local_date.isoformat(),
        "date_label": date_label(ctx.lang, x.local_date), "amount": M(ctx, x.amount_paise),
        "personal_amount": M(ctx, x.personal_amount_paise), "direction": x.direction, "mode": x.mode, "status": x.status,
        "merchant": x.merchant_name or (x.counterparty_name or ""), "merchant_key": x.merchant,
        "category_id": x.category, "category": category_name(cat, ctx.lang) if cat else x.category,
        "emoji": cat.emoji if cat else "", "spend_class": x.spend_class, "narration": x.narration,
        "account": f"{(acct.institution_code or acct.institution)} {acct.masked_number[-4:]}" if acct else "",
        "account_id": x.account_id, "is_split": x.group_expense_id is not None, "group_id": x.group_id,
        "source": x.source, "note": x.note, "recurring": x.recurring_item_id is not None,
    }


def find_transactions(
    ctx: Ctx, *, q: str | None = None, category: str | None = None, direction: str | None = None,
    period: str | None = None, date_from: date | None = None, date_to: date | None = None,
    min_paise: int | None = None, max_paise: int | None = None, account_id: str | None = None,
    spend_class: str | None = None, limit: int = 50, offset: int = 0,
) -> dict[str, Any]:
    if period:
        date_from, date_to = _period(ctx, period)
    needle = (q or "").strip().lower()
    hits = []
    for x in reversed(ctx.txns):
        if x.hidden or x.spend_class == "excluded" and not needle:
            continue
        if category and x.category != category:
            continue
        if direction and x.direction != direction:
            continue
        if date_from and x.local_date < date_from:
            continue
        if date_to and x.local_date > date_to:
            continue
        if min_paise is not None and x.amount_paise < min_paise:
            continue
        if max_paise is not None and x.amount_paise > max_paise:
            continue
        if account_id and x.account_id != account_id:
            continue
        if spend_class and x.spend_class != spend_class:
            continue
        if needle and needle not in f"{x.merchant_name} {x.counterparty_name or ''} {x.narration} {x.category}".lower():
            continue
        hits.append(x)
    total_out = sum(x.personal_amount_paise for x in hits if x.direction == "debit" and x.spend_class != "excluded")
    total_in = sum(x.amount_paise for x in hits if x.direction == "credit" and x.spend_class != "excluded")
    page = hits[offset : offset + limit]
    say = t(ctx.lang, "txn.say", count=len(hits), total=M(ctx, total_out or total_in)["spoken"]) if hits else t(ctx.lang, "txn.say_none")
    return {"count": len(hits), "total_out": M(ctx, total_out), "total_in": M(ctx, total_in),
            "items": [txn_row(ctx, x) for x in page], "has_more": offset + limit < len(hits), "say": say}
