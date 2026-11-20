"""Loads everything about one user into memory once per data version.

A persona has about 1,300 transactions, so the ledger computes in Python on a loaded snapshot.
The cache key includes `users.data_version`, which every write bumps.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api import models as m
from core_api.config import today_ist
from core_api.ledger.classify import next_due_date
from core_api.ledger.mathx import month_key


@dataclass
class Expense:
    """One spending event after netting refunds and group splits."""

    day: date
    month: str
    category: str
    paise: int  # negative for a refund
    spend_class: str  # flexible | committed
    txn_id: str


@dataclass
class Ctx:
    user: m.User
    lang: str
    today: date
    month: str
    settings: m.UserSettings | None
    categories: dict[str, m.Category]
    accounts: list[m.Account]
    txns: list[m.Transaction]
    recurring: list[m.RecurringItem]
    loans: list[m.Loan]
    holdings: list[m.Holding]
    pockets: list[m.Pocket]
    adjustments: list[m.PocketAdjustment]
    goals: list[m.Goal]
    contributions: list[m.GoalContribution]
    statements: list[m.CardStatement]
    nav: dict[int, list[tuple[date, Decimal]]]
    by_id: dict[str, m.Transaction] = field(default_factory=dict)
    expenses: list[Expense] = field(default_factory=list)
    next_due: dict[str, date | None] = field(default_factory=dict)
    last_paid: dict[str, date] = field(default_factory=dict)
    memo: dict[str, Any] = field(default_factory=dict)

    def account(self, account_id: str) -> m.Account | None:
        return next((a for a in self.accounts if a.id == account_id), None)


_ref_cache: dict[str, Any] = {}
_ctx_cache: dict[str, tuple[tuple[int, date], Ctx]] = {}
_CTX_CACHE_MAX = 64


async def load_categories(session: AsyncSession) -> dict[str, m.Category]:
    if "categories" not in _ref_cache:
        rows = (await session.execute(select(m.Category))).scalars().all()
        _ref_cache["categories"] = {c.id: c for c in rows}
    return _ref_cache["categories"]  # type: ignore[no-any-return]


async def load_nav(session: AsyncSession) -> dict[int, list[tuple[date, Decimal]]]:
    if "nav" not in _ref_cache:
        out: dict[int, list[tuple[date, Decimal]]] = defaultdict(list)
        rows = (await session.execute(select(m.NavPrice).order_by(m.NavPrice.scheme_code, m.NavPrice.nav_date))).scalars()
        for r in rows:
            out[r.scheme_code].append((r.nav_date, Decimal(r.nav)))
        _ref_cache["nav"] = dict(out)
    return _ref_cache["nav"]  # type: ignore[no-any-return]


def clear_caches() -> None:
    _ref_cache.clear()
    _ctx_cache.clear()


async def bump(session: AsyncSession, user: m.User) -> None:
    """Call after any write that changes numbers. Invalidates the cached context."""
    user.data_version = (user.data_version or 0) + 1
    _ctx_cache.pop(user.id, None)
    await session.flush()


async def load_ctx(session: AsyncSession, user: m.User) -> Ctx:
    today = today_ist()
    key = (user.data_version or 0, today)
    hit = _ctx_cache.get(user.id)
    if hit is not None and hit[0] == key:
        hit[1].user = user
        hit[1].lang = user.language
        return hit[1]

    async def rows(model: Any, order: Any = None) -> list[Any]:
        q = select(model).where(model.user_id == user.id)
        if order is not None:
            q = q.order_by(order)
        return list((await session.execute(q)).scalars().all())

    ctx = make_ctx(
        user,
        today,
        settings=await session.get(m.UserSettings, user.id),
        categories=await load_categories(session),
        accounts=await rows(m.Account),
        txns=await rows(m.Transaction, m.Transaction.occurred_at),
        recurring=await rows(m.RecurringItem),
        loans=await rows(m.Loan),
        holdings=await rows(m.Holding),
        pockets=await rows(m.Pocket, m.Pocket.sort_order),
        adjustments=await rows(m.PocketAdjustment),
        goals=await rows(m.Goal, m.Goal.priority.desc()),
        contributions=await rows(m.GoalContribution),
        statements=await rows(m.CardStatement, m.CardStatement.statement_date),
        nav=await load_nav(session),
    )
    if len(_ctx_cache) >= _CTX_CACHE_MAX:
        _ctx_cache.pop(next(iter(_ctx_cache)))
    _ctx_cache[user.id] = (key, ctx)
    return ctx


def make_ctx(user: m.User, today: date, **parts: Any) -> Ctx:
    """A Ctx from rows already in hand. `load_ctx` reads them from the database; the evals build
    them straight from the dataset. Transactions must be in time order."""
    ctx = Ctx(user=user, lang=user.language, today=today, month=month_key(today), **parts)
    _derive(ctx)
    return ctx


def _derive(ctx: Ctx) -> None:
    ctx.by_id = {t.id: t for t in ctx.txns}
    paid: dict[str, list[date]] = defaultdict(list)
    for t in ctx.txns:
        if t.spend_class == "excluded":
            continue
        if t.recurring_item_id and t.direction == "debit":
            paid[t.recurring_item_id].append(t.local_date)
        if t.direction == "debit" and t.spend_class in ("flexible", "committed"):
            ctx.expenses.append(Expense(t.local_date, t.budget_month, t.category, t.personal_amount_paise, t.spend_class, t.id))
        elif t.direction == "credit" and t.spend_class == "refund":
            orig = ctx.by_id.get(t.refund_of_id or "")
            if orig is not None and orig.spend_class in ("flexible", "committed"):
                amount = min(t.amount_paise, orig.personal_amount_paise)
                ctx.expenses.append(Expense(t.local_date, t.budget_month, orig.category, -amount, orig.spend_class, t.id))
            else:
                ctx.expenses.append(Expense(t.local_date, t.budget_month, "refund", -t.amount_paise, "flexible", t.id))
    for r in ctx.recurring:
        days = sorted(paid.get(r.id, []))
        gaps = sorted((b - a).days for a, b in zip(days, days[1:], strict=False))
        if days:
            ctx.last_paid[r.id] = days[-1]
        if r.status != "active":
            ctx.next_due[r.id] = None
            continue
        ctx.next_due[r.id] = next_due_date(
            cadence=r.cadence, day=r.day, start_date=r.start_date, end_date=r.end_date,
            last_paid=days[-1] if days else None,
            typical_gap_days=gaps[len(gaps) // 2] if gaps else None, today=ctx.today,
        )
