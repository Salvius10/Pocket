"""In-app nudges: at most 2 a day per user, never in quiet hours (postponed to quiet end), deduped."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from typing import Any

from pocket_common.money import money
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api import models as m
from core_api.collab.service import groups_overview
from core_api.config import IST
from core_api.i18n import t
from core_api.ledger import summary
from core_api.ledger.context import Ctx

PRIORITY = ("bill_due", "overspend", "group_request", "goal_reached", "weekly_report", "insight")
HARD_DAILY_MAX = 2


@dataclass
class Candidate:
    kind: str
    dedupe_key: str
    data: dict[str, Any] = field(default_factory=dict)


def _hm(s: str) -> time:
    h, mm = s.split(":")
    return time(int(h), int(mm))


def in_quiet_hours(local: datetime, quiet_start: str, quiet_end: str) -> bool:
    start, end, now = _hm(quiet_start), _hm(quiet_end), local.time()
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end  # window wraps midnight (22:00 -> 08:00)


def delivery_time(local: datetime, quiet_start: str, quiet_end: str) -> datetime:
    """When a nudge created at `local` (IST) may be shown: now, or the end of quiet hours."""
    if not in_quiet_hours(local, quiet_start, quiet_end):
        return local
    end = _hm(quiet_end)
    target = local.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return target


def pick(candidates: list[Candidate], already_keys: set[str], counts_by_day: dict[Any, int], daily_max: int,
         now_local: datetime, quiet_start: str, quiet_end: str) -> list[tuple[Candidate, datetime]]:
    """Pure planner: priority order, dedupe, and the per-day cap counted on the delivery day."""
    cap = max(0, min(HARD_DAILY_MAX, daily_max))
    counts = dict(counts_by_day)
    when = delivery_time(now_local, quiet_start, quiet_end)
    out: list[tuple[Candidate, datetime]] = []
    for c in sorted(candidates, key=lambda c: PRIORITY.index(c.kind) if c.kind in PRIORITY else len(PRIORITY)):
        if c.dedupe_key in already_keys:
            continue
        if counts.get(when.date(), 0) >= cap:
            break
        counts[when.date()] = counts.get(when.date(), 0) + 1
        already_keys = already_keys | {c.dedupe_key}
        out.append((c, when))
    return out


async def candidates_for(session: AsyncSession, ctx: Ctx) -> list[Candidate]:
    out: list[Candidate] = []
    for b in summary.bills(ctx, 3)["upcoming"]:
        if 0 <= b["days_until"] <= 2:
            out.append(Candidate("bill_due", f"bill:{b['id']}:{b['due_date']}",
                                 {"name": b["name"], "amount_paise": b["amount"]["paise"], "days": b["days_until"]}))
    for p in summary.pockets(ctx):
        if p["status"] == "over":
            out.append(Candidate("overspend", f"overspend:{p['id']}:{ctx.month}",
                                 {"name": p["name"], "spent_paise": p["spent"]["paise"], "limit_paise": p["limit"]["paise"]}))
    for g in await groups_overview(session, ctx.user):
        if g["my_position"] == "owes":
            out.append(Candidate("group_request", f"group:{g['id']}:{g['my_balance']['paise']}",
                                 {"group": g["name"], "amount_paise": -g["my_balance"]["paise"], "group_id": g["id"]}))
    for g in summary.goals(ctx):
        if g["status"] == "reached":
            out.append(Candidate("goal_reached", f"goal:{g['id']}",
                                 {"name": g["name"], "saved_paise": g["saved"]["paise"], "target_paise": g["target"]["paise"]}))
    if ctx.today.weekday() == 0:
        week = summary.cash_flow(ctx)["weeks"][-2]
        out.append(Candidate("weekly_report", f"week:{week['start']}",
                             {"spend_paise": week["spend"]["paise"], "income_paise": week["income"]["paise"]}))
    top = (await session.execute(
        select(m.Insight).where(m.Insight.user_id == ctx.user.id, m.Insight.status == "active")
        .order_by(m.Insight.severity.desc(), m.Insight.impact_paise.desc()).limit(1)
    )).scalars().first()
    if top is not None and top.type != "overspend_pocket":
        out.append(Candidate("insight", f"insight:{top.fingerprint}", {"insight_id": top.id, "type": top.type, "data": top.data}))
    return out


async def plan_nudges(session: AsyncSession, ctx: Ctx, now: datetime | None = None) -> list[m.Nudge]:
    now_local = (now or datetime.now(UTC)).astimezone(IST)
    s = ctx.settings
    daily_max = s.nudge_daily_max if s else 2
    qs, qe = (s.quiet_start, s.quiet_end) if s else ("22:00", "08:00")
    existing = list((await session.execute(select(m.Nudge).where(m.Nudge.user_id == ctx.user.id))).scalars())
    counts: dict[Any, int] = {}
    for n in existing:
        counts[n.local_day] = counts.get(n.local_day, 0) + 1
    chosen = pick(await candidates_for(session, ctx), {n.dedupe_key for n in existing}, counts, daily_max, now_local, qs, qe)
    rows = []
    for c, when in chosen:
        row = m.Nudge(user_id=ctx.user.id, kind=c.kind, dedupe_key=c.dedupe_key, data=c.data, scheduled_at=when.astimezone(UTC),
                      local_day=when.date(), status="scheduled")
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


def nudge_view(ctx: Ctx, n: m.Nudge) -> dict[str, Any]:
    lang, d = ctx.lang, n.data or {}

    def disp(key: str) -> str:
        return money(int(d.get(key, 0)), lang)["display"]

    if n.kind == "bill_due":
        days = int(d.get("days", 0))
        when = t(lang, "when.today") if days == 0 else t(lang, "when.tomorrow") if days == 1 else t(lang, "when.in_days", n=days)
        title, body = t(lang, "nudge.bill_due.title", name=d.get("name", ""), when=when), t(lang, "nudge.bill_due.body", amt=disp("amount_paise"))
    elif n.kind == "overspend":
        title = t(lang, "nudge.overspend.title", name=d.get("name", ""))
        body = t(lang, "nudge.overspend.body", spent=disp("spent_paise"), limit=disp("limit_paise"))
    elif n.kind == "group_request":
        title, body = t(lang, "nudge.group_request.title", group=d.get("group", ""), amt=disp("amount_paise")), t(lang, "nudge.group_request.body")
    elif n.kind == "goal_reached":
        title = t(lang, "nudge.goal_reached.title", name=d.get("name", ""))
        body = t(lang, "nudge.goal_reached.body", saved=disp("saved_paise"), target=disp("target_paise"))
    elif n.kind == "weekly_report":
        title = t(lang, "nudge.weekly_report.title")
        body = t(lang, "nudge.weekly_report.body", spend=disp("spend_paise"), income=disp("income_paise"))
    else:
        from core_api.insights.engine import render

        words = render(ctx, str(d.get("type", "")), d.get("data") or {})
        title, body = words["title"], words["body"]
    return {"id": n.id, "kind": n.kind, "title": title, "body": body, "status": n.status,
            "scheduled_at": n.scheduled_at.isoformat(), "group_id": d.get("group_id"), "insight_id": d.get("insight_id")}


async def due_nudges(session: AsyncSession, ctx: Ctx, now: datetime | None = None) -> list[dict[str, Any]]:
    """Nudges whose time has come and that the user has not dismissed. Marks them shown."""
    now = now or datetime.now(UTC)
    rows = list((await session.execute(
        select(m.Nudge).where(m.Nudge.user_id == ctx.user.id, m.Nudge.status != "dismissed", m.Nudge.scheduled_at <= now)
        .order_by(m.Nudge.scheduled_at.desc()).limit(10)
    )).scalars())
    for n in rows:
        if n.status == "scheduled":
            n.status, n.shown_at = "shown", now
    return [nudge_view(ctx, n) for n in rows]
