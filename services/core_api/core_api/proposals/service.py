"""Proposals: every write the mascot suggests. Nothing here executes until a tap accepts it.

`create_proposal` validates and builds the confirm card. `accept_proposal` is the only executor;
it runs in one transaction and writes an audit row. A spoken "yes" has no path to it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from pocket_common.money import money
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api import models as m
from core_api.config import IST, now_utc
from core_api.i18n import category_name, t
from core_api.ledger import mathx, summary
from core_api.ledger.context import Ctx, bump

KINDS = ("set_goal", "create_pocket", "move_between_pockets", "add_transaction")
MASCOT_TTL = timedelta(minutes=10)
MAX_PAISE = 10_00_00_000 * 100  # ₹10 crore: anything above is a mistake


class ProposalError(ValueError):
    pass


def _amount(payload: dict[str, Any], key: str = "amount_paise") -> int:
    v = payload.get(key)
    if not isinstance(v, int) or isinstance(v, bool) or v <= 0 or v > MAX_PAISE:
        raise ProposalError(f"{key} must be a positive whole number of paise")
    return v


def _find(items: list[Any], item_id: str | None, name: str | None) -> Any | None:
    if item_id:
        hit = next((i for i in items if i.id == item_id), None)
        if hit is not None:
            return hit
    if name:
        needle = name.strip().lower()
        exact = next((i for i in items if i.name.lower() == needle), None)
        return exact or next((i for i in items if needle in i.name.lower() or i.name.lower() in needle), None)
    return None


def normalise(ctx: Ctx, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate against the user's real data and resolve names to ids. Raises ProposalError."""
    if kind not in KINDS:
        raise ProposalError(f"unknown proposal kind: {kind}")
    if kind == "move_between_pockets":
        amount = _amount(payload)
        src = _find([p for p in ctx.pockets if p.status != "archived"], payload.get("from_pocket_id"), payload.get("from"))
        if src is None:
            raise ProposalError("source pocket not found")
        dst_goal = _find([g for g in ctx.goals if g.status == "active"], payload.get("to_goal_id"), payload.get("to"))
        dst_pocket = None
        if dst_goal is None or payload.get("to_pocket_id"):
            dst_pocket = _find([p for p in ctx.pockets if p.status != "archived" and p.id != src.id], payload.get("to_pocket_id"), payload.get("to"))
            if dst_pocket is not None:
                dst_goal = None
        if dst_goal is None and dst_pocket is None:
            raise ProposalError("destination pocket or goal not found")
        left = summary.pocket_limit(ctx, src) - summary.pocket_spent(ctx, src)
        if amount > left:
            raise ProposalError("the source pocket does not have that much left this month")
        out = {"from_pocket_id": src.id, "amount_paise": amount}
        if dst_goal is not None:
            out["to_goal_id"] = dst_goal.id
        else:
            assert dst_pocket is not None
            out["to_pocket_id"] = dst_pocket.id
        return out
    if kind == "set_goal":
        name = str(payload.get("name") or "").strip()[:80]
        existing = _find(list(ctx.goals), payload.get("goal_id"), name or None) if (payload.get("goal_id") or name) else None
        if not name and existing is None:
            raise ProposalError("a goal needs a name")
        target = payload.get("target_paise")
        if existing is None or target is not None:
            target = _amount(payload, "target_paise")
        deadline = payload.get("deadline")
        if deadline:
            try:
                d = date.fromisoformat(str(deadline)[:10])
            except ValueError as exc:
                raise ProposalError("deadline must be a date like 2027-03-31") from exc
            if d <= ctx.today:
                raise ProposalError("deadline must be in the future")
            deadline = d.isoformat()
        monthly = payload.get("monthly_plan_paise")
        if monthly is not None:
            monthly = _amount(payload, "monthly_plan_paise")
        return {"goal_id": existing.id if existing else None, "name": name or (existing.name if existing else ""),
                "emoji": str(payload.get("emoji") or (existing.emoji if existing else "🎯"))[:8],
                "target_paise": target if target is not None else (existing.target_paise if existing else 0),
                "deadline": deadline or (existing.deadline.isoformat() if existing and existing.deadline else None),
                "monthly_plan_paise": monthly}
    if kind == "create_pocket":
        name = str(payload.get("name") or "").strip()[:80]
        if not name:
            raise ProposalError("a pocket needs a name")
        if any(p.name.lower() == name.lower() and p.status != "archived" for p in ctx.pockets):
            raise ProposalError("a pocket with that name already exists")
        cats = [c for c in (payload.get("category_ids") or []) if c in ctx.categories]
        if not cats:
            raise ProposalError("a pocket needs at least one known category")
        return {"name": name, "emoji": str(payload.get("emoji") or "👛")[:8], "monthly_limit_paise": _amount(payload, "monthly_limit_paise"),
                "category_ids": cats}
    # add_transaction: manual cash entry
    amount = _amount(payload)
    direction = payload.get("direction") or "debit"
    if direction not in ("debit", "credit"):
        raise ProposalError("direction must be debit or credit")
    category = payload.get("category_id") or ("other_expense" if direction == "debit" else "other_income")
    if category not in ctx.categories:
        raise ProposalError("unknown category")
    when = payload.get("date")
    try:
        day = date.fromisoformat(str(when)[:10]) if when else ctx.today
    except ValueError as exc:
        raise ProposalError("date must look like 2026-11-20") from exc
    if day > ctx.today or day < ctx.today - timedelta(days=90):
        raise ProposalError("date must be within the last 90 days")
    return {"amount_paise": amount, "direction": direction, "category_id": category,
            "description": str(payload.get("description") or "").strip()[:120] or "Cash", "date": day.isoformat()}


def build_preview(ctx: Ctx, kind: str, p: dict[str, Any]) -> dict[str, Any]:
    """The confirm card. Code builds every word and number on it."""

    def d(paise: int) -> str:
        return money(paise, ctx.lang)["display"]

    def s(paise: int) -> str:
        return money(paise, ctx.lang)["spoken"]

    def card(title_key: str, body_key: str, disp: dict[str, Any], spok: dict[str, Any]) -> dict[str, Any]:
        return {"title": t(ctx.lang, title_key, **disp), "body": t(ctx.lang, body_key, **disp),
                "say": t(ctx.lang, title_key, **spok)}

    if kind == "move_between_pockets":
        src = next(x for x in ctx.pockets if x.id == p["from_pocket_id"])
        src_left = summary.pocket_limit(ctx, src) - summary.pocket_spent(ctx, src) - p["amount_paise"]
        if p.get("to_goal_id"):
            goal = next(g for g in ctx.goals if g.id == p["to_goal_id"])
            after = summary.goal_saved(ctx, goal.id) + p["amount_paise"]
            dst_name, dst_emoji = goal.name, goal.emoji
        else:
            dst = next(x for x in ctx.pockets if x.id == p["to_pocket_id"])
            after = summary.pocket_limit(ctx, dst) + p["amount_paise"]
            dst_name, dst_emoji = dst.name, dst.emoji
        out = card("proposal.move.title", "proposal.move.body",
                   {"amt": d(p["amount_paise"]), "src": src.name, "dst": dst_name, "src_left": d(src_left), "dst_after": d(after)},
                   {"amt": s(p["amount_paise"]), "src": src.name, "dst": dst_name})
        out.update(amount=dict(money(p["amount_paise"], ctx.lang)), from_name=src.name, from_emoji=src.emoji, to_name=dst_name, to_emoji=dst_emoji)
        return out
    if kind == "set_goal":
        need = 0
        if p.get("monthly_plan_paise"):
            need = p["monthly_plan_paise"]
        elif p.get("deadline"):
            saved = summary.goal_saved(ctx, p["goal_id"]) if p.get("goal_id") else 0
            need = -(-max(0, p["target_paise"] - saved) // mathx.months_between(ctx.today, date.fromisoformat(p["deadline"])))
        out = card("proposal.goal.title", "proposal.goal.body" if need else "proposal.goal.body_open",
                   {"name": p["name"], "target": d(p["target_paise"]), "need": d(need)}, {"name": p["name"], "target": s(p["target_paise"])})
        out.update(amount=dict(money(p["target_paise"], ctx.lang)), to_name=p["name"], to_emoji=p["emoji"])
        return out
    if kind == "create_pocket":
        cats = set(p["category_ids"])
        spent = max(0, sum(e.paise for e in ctx.expenses if e.month == ctx.month and e.category in cats))
        out = card("proposal.pocket.title", "proposal.pocket.body",
                   {"name": p["name"], "limit": d(p["monthly_limit_paise"]), "spent": d(spent)}, {"name": p["name"], "limit": s(p["monthly_limit_paise"])})
        out.update(amount=dict(money(p["monthly_limit_paise"], ctx.lang)), to_name=p["name"], to_emoji=p["emoji"])
        return out
    cat = ctx.categories[p["category_id"]]
    key = "proposal.txn.title" if p["direction"] == "debit" else "proposal.txn.title_in"
    out = card(key, "proposal.txn.body", {"amt": d(p["amount_paise"]), "what": p["description"], "category": category_name(cat, ctx.lang)},
               {"amt": s(p["amount_paise"])})
    out.update(amount=dict(money(p["amount_paise"], ctx.lang)), to_name=p["description"], to_emoji=cat.emoji)
    return out


async def create_proposal(
    session: AsyncSession, ctx: Ctx, kind: str, payload: dict[str, Any], *, source: str = "mascot", insight_id: str | None = None
) -> m.Proposal:
    clean = normalise(ctx, kind, payload)
    prop = m.Proposal(
        user_id=ctx.user.id, kind=kind, payload=clean, preview=build_preview(ctx, kind, clean), source=source, insight_id=insight_id,
        status="pending", expires_at=now_utc() + MASCOT_TTL if source == "mascot" else None,
    )
    session.add(prop)
    await session.flush()
    return prop


def proposal_view(ctx: Ctx, p: m.Proposal) -> dict[str, Any]:
    preview = dict(p.preview or {})
    if p.status == "pending":
        try:
            preview = build_preview(ctx, p.kind, p.payload)  # numbers stay current
        except (StopIteration, KeyError, ProposalError):
            pass
    return {"id": p.id, "kind": p.kind, "status": p.status, "source": p.source, "insight_id": p.insight_id, **preview,
            "expires_at": p.expires_at.isoformat() if p.expires_at else None}


def _expired(p: m.Proposal) -> bool:
    return p.expires_at is not None and p.expires_at <= now_utc()


async def list_pending(session: AsyncSession, ctx: Ctx) -> list[dict[str, Any]]:
    rows = (await session.execute(
        select(m.Proposal).where(m.Proposal.user_id == ctx.user.id, m.Proposal.status == "pending").order_by(m.Proposal.created_at.desc())
    )).scalars()
    out = []
    for p in rows:
        if _expired(p):
            p.status = "expired"
            continue
        out.append(proposal_view(ctx, p))
    return out


async def decline_proposal(session: AsyncSession, user: m.User, proposal_id: str) -> m.Proposal:
    p = await session.get(m.Proposal, proposal_id)
    if p is None or p.user_id != user.id:
        raise ProposalError("proposal not found")
    if p.status == "pending":
        p.status, p.decided_at = "declined", now_utc()
        session.add(m.AuditLog(user_id=user.id, action="proposal.decline", entity="proposal", entity_id=p.id, detail={"kind": p.kind}))
    return p


async def accept_proposal(session: AsyncSession, ctx: Ctx, proposal_id: str) -> m.Proposal:
    """Execute a pending proposal. Caller commits; any error leaves nothing half-done."""
    p = await session.get(m.Proposal, proposal_id, with_for_update=True)
    if p is None or p.user_id != ctx.user.id:
        raise ProposalError("proposal not found")
    if p.status == "accepted":
        return p  # idempotent: a double tap does not run it twice
    if p.status != "pending":
        raise ProposalError(f"proposal is {p.status}")
    if _expired(p):
        p.status = "expired"
        raise ProposalError("proposal has expired")
    payload = normalise(ctx, p.kind, p.payload)  # re-validate against today's numbers
    detail: dict[str, Any] = {"kind": p.kind, "payload": payload}
    user_id, month = ctx.user.id, ctx.month
    if p.kind == "move_between_pockets":
        amount = payload["amount_paise"]
        session.add(m.PocketAdjustment(user_id=user_id, pocket_id=payload["from_pocket_id"], month=month, delta_paise=-amount,
                                       reason="move", proposal_id=p.id))
        if payload.get("to_goal_id"):
            session.add(m.GoalContribution(user_id=user_id, goal_id=payload["to_goal_id"], amount_paise=amount, month=month,
                                           source="proposal", note="From pocket", proposal_id=p.id))
        else:
            session.add(m.PocketAdjustment(user_id=user_id, pocket_id=payload["to_pocket_id"], month=month, delta_paise=amount,
                                           reason="move", proposal_id=p.id))
    elif p.kind == "set_goal":
        deadline = date.fromisoformat(payload["deadline"]) if payload.get("deadline") else None
        if payload.get("goal_id"):
            goal = await session.get(m.Goal, payload["goal_id"])
            assert goal is not None and goal.user_id == user_id
            goal.name, goal.target_paise, goal.deadline = payload["name"], payload["target_paise"], deadline
            if payload.get("monthly_plan_paise"):
                goal.monthly_plan_paise = payload["monthly_plan_paise"]
        else:
            goal = m.Goal(user_id=user_id, name=payload["name"], emoji=payload["emoji"], target_paise=payload["target_paise"],
                          deadline=deadline, monthly_plan_paise=payload.get("monthly_plan_paise"), priority=0, created_by="mascot")
            session.add(goal)
            await session.flush()
        detail["goal_id"] = goal.id
    elif p.kind == "create_pocket":
        pocket = m.Pocket(user_id=user_id, name=payload["name"], emoji=payload["emoji"], monthly_limit_paise=payload["monthly_limit_paise"],
                          category_ids=payload["category_ids"], sort_order=len(ctx.pockets), created_by="mascot")
        session.add(pocket)
        await session.flush()
        detail["pocket_id"] = pocket.id
    else:
        txn = await add_manual_transaction(session, ctx, payload)
        detail["transaction_id"] = txn.id
    p.status, p.decided_at = "accepted", now_utc()
    if p.insight_id:
        ins = await session.get(m.Insight, p.insight_id)
        if ins is not None:
            ins.proposal_id = None
    session.add(m.AuditLog(user_id=user_id, action="proposal.accept", entity="proposal", entity_id=p.id, detail=detail))
    await bump(session, ctx.user)
    return p


async def cash_account(session: AsyncSession, ctx: Ctx) -> m.Account:
    acct = next((a for a in ctx.accounts if a.type == "cash"), None)
    if acct is None:
        acct = m.Account(user_id=ctx.user.id, institution=t(ctx.lang, "label.cash"), institution_code="CASH", type="cash", masked_number="", role="cash")
        session.add(acct)
        await session.flush()
    return acct


async def add_manual_transaction(session: AsyncSession, ctx: Ctx, payload: dict[str, Any]) -> m.Transaction:
    from core_api.ledger.classify import spend_class

    acct = await cash_account(session, ctx)
    day = date.fromisoformat(payload["date"])
    now_ist = datetime.now(IST)
    occurred = datetime(day.year, day.month, day.day, now_ist.hour if day == ctx.today else 12, now_ist.minute if day == ctx.today else 0, tzinfo=IST)
    cat = ctx.categories[payload["category_id"]]
    txn = m.Transaction(
        user_id=ctx.user.id, account_id=acct.id, occurred_at=occurred.astimezone(UTC), local_date=day,
        budget_month=mathx.budget_month_for(day, payload["category_id"] == "salary"), amount_paise=payload["amount_paise"],
        personal_amount_paise=payload["amount_paise"], direction=payload["direction"], mode="cash", status="success", kind="manual",
        merchant=None, merchant_name=payload["description"], category=payload["category_id"],
        spend_class=spend_class(status="success", hidden=False, is_reversal=False, category_kind=cat.kind,
                                category_default_class=cat.default_class, recurring_kind=None),
        narration=payload["description"], source="manual",
    )
    session.add(txn)
    await session.flush()
    return txn
