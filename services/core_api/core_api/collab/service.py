"""Collab: groups, splits, balances and UPI settle-up links. Pocket tracks; it never holds money."""

from __future__ import annotations

import secrets
from collections import defaultdict
from datetime import date, timedelta
from typing import Any
from urllib.parse import quote

from pocket_common.money import money, pct_half_up
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api import models as m
from core_api.config import IST, now_utc, today_ist
from core_api.i18n import date_label, t
from core_api.ledger import mathx
from core_api.ledger.context import bump

GROUP_TYPES = ("family", "trip", "flatmates", "custom")
SETTLED = ("marked_paid", "confirmed")
STATUS_FLOW = {"pending": ("link_opened", "marked_paid"), "link_opened": ("marked_paid",), "marked_paid": ("confirmed",), "confirmed": ()}
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class CollabError(ValueError):
    pass


def upi_link(vpa: str, name: str, amount_paise: int, note: str) -> str:
    """upi://pay deep link. The amount is rupees with two decimals, straight from integer paise."""
    rupees = f"{amount_paise // 100}.{amount_paise % 100:02d}"
    return f"upi://pay?pa={quote(vpa, safe='@.-_')}&pn={quote(name)}&am={rupees}&cu=INR&tn={quote(note[:50])}"


async def _member_of(session: AsyncSession, group_id: str, user_id: str) -> m.GroupMember:
    me = (await session.execute(
        select(m.GroupMember).where(m.GroupMember.group_id == group_id, m.GroupMember.user_id == user_id)
    )).scalars().first()
    if me is None:
        raise CollabError("group not found")  # same answer whether it exists or not: membership is required
    return me


async def _members(session: AsyncSession, group_id: str) -> list[m.GroupMember]:
    return list((await session.execute(
        select(m.GroupMember).where(m.GroupMember.group_id == group_id).order_by(m.GroupMember.join_order)
    )).scalars())


async def _balances(session: AsyncSession, group_id: str, members: list[m.GroupMember]) -> dict[str, int]:
    bal: dict[str, int] = {mm.id: 0 for mm in members}
    expenses = list((await session.execute(
        select(m.GroupExpense).where(m.GroupExpense.group_id == group_id, m.GroupExpense.is_deleted.is_(False))
    )).scalars())
    live = {e.id for e in expenses}
    for e in expenses:
        bal[e.paid_by_member_id] = bal.get(e.paid_by_member_id, 0) + e.amount_paise
    for s in (await session.execute(select(m.GroupExpenseShare).where(m.GroupExpenseShare.group_id == group_id))).scalars():
        if s.expense_id in live:
            bal[s.member_id] = bal.get(s.member_id, 0) - s.share_paise
    for st in (await session.execute(select(m.Settlement).where(m.Settlement.group_id == group_id))).scalars():
        if st.status in SETTLED:
            bal[st.from_member_id] = bal.get(st.from_member_id, 0) + st.amount_paise
            bal[st.to_member_id] = bal.get(st.to_member_id, 0) - st.amount_paise
    return bal


async def groups_overview(session: AsyncSession, user: m.User) -> list[dict[str, Any]]:
    lang = user.language
    mine = list((await session.execute(select(m.GroupMember).where(m.GroupMember.user_id == user.id))).scalars())
    out = []
    for me in mine:
        g = await session.get(m.Group, me.group_id)
        if g is None or g.status != "active":
            continue
        members = await _members(session, g.id)
        bal = await _balances(session, g.id, members)
        pot = sum((await session.execute(select(m.GroupPotContribution.amount_paise).where(m.GroupPotContribution.group_id == g.id))).scalars())
        mine_bal = bal.get(me.id, 0)
        if mine_bal > 0:
            say = t(lang, "groups.say_owed", group=g.name, amt=money(mine_bal, lang)["spoken"])
        elif mine_bal < 0:
            say = t(lang, "groups.say_owe", group=g.name, amt=money(-mine_bal, lang)["spoken"])
        else:
            say = t(lang, "groups.say_even", group=g.name)
        if g.pot_target_paise:
            say += " " + t(lang, "groups.say_pot", have=money(pot, lang)["spoken"], target=money(g.pot_target_paise, lang)["spoken"])
        out.append({
            "id": g.id, "type": g.type, "name": g.name, "emoji": g.emoji, "member_count": len(members),
            "members": [{"id": mm.id, "name": mm.display_name, "is_me": mm.id == me.id} for mm in members],
            "my_balance": dict(money(mine_bal, lang)), "my_balance_abs": dict(money(abs(mine_bal), lang)),
            "my_position": "owed" if mine_bal > 0 else "owes" if mine_bal < 0 else "even",
            "pot": {"saved": dict(money(pot, lang)), "target": dict(money(g.pot_target_paise, lang)),
                    "pct": min(100, pct_half_up(pot, g.pot_target_paise)),
                    "deadline": g.pot_deadline.isoformat() if g.pot_deadline else None,
                    "deadline_label": date_label(lang, g.pot_deadline) if g.pot_deadline else None} if g.pot_target_paise else None,
            "budget": dict(money(g.budget_monthly_paise, lang)) if g.budget_monthly_paise else None, "say": say,
        })
    return sorted(out, key=lambda x: x["name"])


async def group_detail(session: AsyncSession, user: m.User, group_id: str) -> dict[str, Any]:
    lang = user.language
    me = await _member_of(session, group_id, user.id)
    g = await session.get(m.Group, group_id)
    assert g is not None
    members = await _members(session, group_id)
    names = {mm.id: mm.display_name for mm in members}
    bal = await _balances(session, group_id, members)
    plan = mathx.settle_plan(bal) if any(bal.values()) else []
    expenses = list((await session.execute(
        select(m.GroupExpense).where(m.GroupExpense.group_id == group_id, m.GroupExpense.is_deleted.is_(False))
        .order_by(m.GroupExpense.occurred_at.desc())
    )).scalars())
    shares: dict[str, dict[str, int]] = defaultdict(dict)
    for s in (await session.execute(select(m.GroupExpenseShare).where(m.GroupExpenseShare.group_id == group_id))).scalars():
        shares[s.expense_id][s.member_id] = s.share_paise
    today = today_ist()
    month_spend = sum(e.amount_paise for e in expenses if mathx.month_key(e.occurred_at.astimezone(IST).date()) == mathx.month_key(today))
    pots = list((await session.execute(
        select(m.GroupPotContribution).where(m.GroupPotContribution.group_id == group_id).order_by(m.GroupPotContribution.occurred_at.desc())
    )).scalars())
    pot_total = sum(p.amount_paise for p in pots)
    pot_by_member: dict[str, int] = defaultdict(int)
    for p in pots:
        pot_by_member[p.member_id] += p.amount_paise
    settlements = list((await session.execute(
        select(m.Settlement).where(m.Settlement.group_id == group_id).order_by(m.Settlement.created_at.desc())
    )).scalars())
    invite = (await session.execute(select(m.GroupInvite).where(m.GroupInvite.group_id == group_id))).scalars().first()

    def M(p: int) -> dict[str, Any]:
        return dict(money(p, lang))

    return {
        "id": g.id, "type": g.type, "name": g.name, "emoji": g.emoji, "my_member_id": me.id, "is_owner": g.owner_user_id == user.id,
        "members": [{"id": mm.id, "name": mm.display_name, "is_me": mm.id == me.id, "is_guest": mm.user_id is None, "vpa": mm.vpa,
                     "balance": M(bal.get(mm.id, 0)), "balance_abs": M(abs(bal.get(mm.id, 0))),
                     "position": "owed" if bal.get(mm.id, 0) > 0 else "owes" if bal.get(mm.id, 0) < 0 else "even",
                     "pot": M(pot_by_member.get(mm.id, 0))} for mm in members],
        "settle_plan": [{"from_id": p.from_id, "from_name": names.get(p.from_id, ""), "to_id": p.to_id, "to_name": names.get(p.to_id, ""),
                         "amount": M(p.amount_paise), "involves_me": me.id in (p.from_id, p.to_id), "i_pay": p.from_id == me.id}
                        for p in plan],
        "budget": {"limit": M(g.budget_monthly_paise), "spent": M(month_spend), "left": M(g.budget_monthly_paise - month_spend),
                   "pct": pct_half_up(month_spend, g.budget_monthly_paise)} if g.budget_monthly_paise else None,
        "pot": {"saved": M(pot_total), "target": M(g.pot_target_paise), "left": M(max(0, g.pot_target_paise - pot_total)),
                "pct": min(100, pct_half_up(pot_total, g.pot_target_paise)),
                "deadline": g.pot_deadline.isoformat() if g.pot_deadline else None,
                "deadline_label": date_label(lang, g.pot_deadline) if g.pot_deadline else None} if g.pot_target_paise else None,
        "expenses": [{"id": e.id, "description": e.description, "amount": M(e.amount_paise), "paid_by": names.get(e.paid_by_member_id, ""),
                      "paid_by_me": e.paid_by_member_id == me.id, "split_method": e.split_method, "category_id": e.category,
                      "date": e.occurred_at.astimezone(IST).date().isoformat(), "date_label": date_label(lang, e.occurred_at.astimezone(IST).date()),
                      "my_share": M(shares[e.id].get(me.id, 0)), "member_count": len(shares[e.id])} for e in expenses[:60]],
        "expense_count": len(expenses), "expense_total": M(sum(e.amount_paise for e in expenses)),
        "settlements": [{"id": s.id, "from_id": s.from_member_id, "from_name": names.get(s.from_member_id, ""), "to_id": s.to_member_id,
                         "to_name": names.get(s.to_member_id, ""), "amount": M(s.amount_paise), "status": s.status, "upi_link": s.upi_link,
                         "i_pay": s.from_member_id == me.id, "i_receive": s.to_member_id == me.id,
                         "date_label": date_label(lang, s.created_at.astimezone(IST).date())} for s in settlements[:30]],
        "invite_code": invite.code if invite else None,
        "my_sharing": me.sharing or {"category_ids": [], "show_transactions": False, "goal_ids": []},
    }


async def create_group(session: AsyncSession, user: m.User, *, name: str, type_: str, emoji: str = "",
                       budget_monthly_paise: int | None = None, pot_target_paise: int | None = None, pot_deadline: date | None = None) -> m.Group:
    if type_ not in GROUP_TYPES:
        raise CollabError("unknown group type")
    name = name.strip()[:80]
    if not name:
        raise CollabError("a group needs a name")
    g = m.Group(type=type_, name=name, emoji=emoji[:24], owner_user_id=user.id, budget_monthly_paise=budget_monthly_paise,
                pot_target_paise=pot_target_paise, pot_deadline=pot_deadline)
    session.add(g)
    await session.flush()
    session.add(m.GroupMember(group_id=g.id, user_id=user.id, display_name=user.display_name or user.first_name or "You", role="owner",
                              join_order=0, sharing={"category_ids": [], "show_transactions": False, "goal_ids": []}))
    await new_invite(session, user, g.id, check=False)
    await session.flush()
    return g


async def new_invite(session: AsyncSession, user: m.User, group_id: str, check: bool = True) -> m.GroupInvite:
    if check:
        await _member_of(session, group_id, user.id)
    for _ in range(8):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if await session.get(m.GroupInvite, code) is None:
            inv = m.GroupInvite(code=code, group_id=group_id, created_by=user.id, max_uses=10, uses=0,
                                expires_at=today_ist() + timedelta(days=30))
            session.add(inv)
            return inv
    raise CollabError("could not create an invite code")


async def join_group(session: AsyncSession, user: m.User, code: str) -> m.Group:
    inv = await session.get(m.GroupInvite, code.strip().upper())
    if inv is None or inv.uses >= inv.max_uses or (inv.expires_at is not None and inv.expires_at < today_ist()):
        raise CollabError("that invite code is not valid")
    g = await session.get(m.Group, inv.group_id)
    if g is None:
        raise CollabError("that invite code is not valid")
    members = await _members(session, g.id)
    if any(mm.user_id == user.id for mm in members):
        return g
    session.add(m.GroupMember(group_id=g.id, user_id=user.id, display_name=user.display_name or user.first_name or "Member", role="member",
                              join_order=max((mm.join_order for mm in members), default=-1) + 1,
                              sharing={"category_ids": [], "show_transactions": False, "goal_ids": []}))
    inv.uses += 1
    return g


async def add_guest(session: AsyncSession, user: m.User, group_id: str, name: str, vpa: str | None) -> m.GroupMember:
    await _member_of(session, group_id, user.id)
    name = name.strip()[:80]
    if not name:
        raise CollabError("a guest needs a name")
    if vpa and ("@" not in vpa or " " in vpa):
        raise CollabError("that UPI ID does not look right")
    members = await _members(session, group_id)
    guest = m.GroupMember(group_id=group_id, user_id=None, display_name=name, vpa=(vpa or None), role="guest",
                          join_order=max((mm.join_order for mm in members), default=-1) + 1, sharing={})
    session.add(guest)
    await session.flush()
    return guest


async def add_expense(
    session: AsyncSession, user: m.User, group_id: str, *, amount_paise: int, description: str, paid_by_member_id: str | None,
    split_method: str, split_input: dict[str, Any], category: str | None = None, linked_transaction_id: str | None = None,
) -> m.GroupExpense:
    me = await _member_of(session, group_id, user.id)
    members = await _members(session, group_id)
    ids = [mm.id for mm in members]
    if amount_paise <= 0:
        raise CollabError("amount must be more than zero")
    payer = paid_by_member_id or me.id
    if payer not in ids:
        raise CollabError("payer is not in this group")
    try:
        if split_method == "equal":
            chosen = [i for i in ids if i in set(split_input.get("member_ids") or ids)]
            shares = mathx.split_equal(amount_paise, chosen)
            split_input = {"member_ids": chosen}
        elif split_method == "percent":
            bps = {k: int(v) for k, v in (split_input.get("bps") or {}).items() if k in ids}
            shares = mathx.split_percent(amount_paise, {i: bps[i] for i in ids if i in bps})
            split_input = {"bps": bps}
        elif split_method == "exact":
            paise = {k: int(v) for k, v in (split_input.get("paise") or {}).items() if k in ids}
            shares = mathx.split_exact(amount_paise, paise)
            split_input = {"paise": paise}
        else:
            raise CollabError("split must be equal, percent or exact")
    except mathx.SplitError as exc:
        raise CollabError(str(exc)) from exc
    e = m.GroupExpense(group_id=group_id, paid_by_member_id=payer, amount_paise=amount_paise, description=description.strip()[:200] or "Expense",
                       category=category, occurred_at=now_utc(), split_method=split_method, split_input=split_input,
                       linked_transaction_id=linked_transaction_id, created_by_member_id=me.id)
    session.add(e)
    await session.flush()
    for member_id, share in shares.items():
        session.add(m.GroupExpenseShare(expense_id=e.id, member_id=member_id, group_id=group_id, share_paise=share))
    if linked_transaction_id:
        txn = await session.get(m.Transaction, linked_transaction_id)
        if txn is None or txn.user_id != user.id:
            raise CollabError("transaction not found")
        if payer != me.id or txn.amount_paise != amount_paise:
            raise CollabError("a split transaction must be paid by you and match its amount")
        txn.group_expense_id, txn.group_id = e.id, group_id
        txn.personal_amount_paise = min(txn.amount_paise, shares.get(me.id, 0))  # only the user's share counts as their spend
        e.occurred_at = txn.occurred_at
        await bump(session, user)
    return e


async def delete_expense(session: AsyncSession, user: m.User, group_id: str, expense_id: str) -> None:
    await _member_of(session, group_id, user.id)
    e = await session.get(m.GroupExpense, expense_id)
    if e is None or e.group_id != group_id:
        raise CollabError("expense not found")
    e.is_deleted = True
    if e.linked_transaction_id:
        txn = await session.get(m.Transaction, e.linked_transaction_id)
        if txn is not None and txn.user_id == user.id:
            txn.group_expense_id, txn.group_id, txn.personal_amount_paise = None, None, txn.amount_paise
            await bump(session, user)


async def create_settlement(session: AsyncSession, user: m.User, group_id: str, *, from_member_id: str, to_member_id: str, amount_paise: int) -> m.Settlement:
    me = await _member_of(session, group_id, user.id)
    members = {mm.id: mm for mm in await _members(session, group_id)}
    if from_member_id not in members or to_member_id not in members or from_member_id == to_member_id:
        raise CollabError("members are not in this group")
    if amount_paise <= 0:
        raise CollabError("amount must be more than zero")
    g = await session.get(m.Group, group_id)
    assert g is not None
    payee = members[to_member_id]
    link = upi_link(payee.vpa, payee.display_name, amount_paise, f"Pocket: {g.name}") if payee.vpa else None
    s = m.Settlement(group_id=group_id, from_member_id=from_member_id, to_member_id=to_member_id, amount_paise=amount_paise,
                     status="pending", upi_link=link, created_by_member_id=me.id)
    session.add(s)
    await session.flush()
    return s


async def set_settlement_status(session: AsyncSession, user: m.User, group_id: str, settlement_id: str, status: str) -> m.Settlement:
    me = await _member_of(session, group_id, user.id)
    s = await session.get(m.Settlement, settlement_id)
    if s is None or s.group_id != group_id:
        raise CollabError("settlement not found")
    if status not in STATUS_FLOW.get(s.status, ()):
        raise CollabError(f"cannot go from {s.status} to {status}")
    if status == "confirmed" and me.id != s.to_member_id:
        payee = await session.get(m.GroupMember, s.to_member_id)
        if payee is None or payee.user_id is not None:
            raise CollabError("only the person who was paid can confirm")  # a guest cannot tap, so any member may confirm for them
    s.status = status
    if status == "marked_paid":
        s.marked_paid_at = now_utc()
    if status == "confirmed":
        s.confirmed_at = now_utc()
    return s


async def add_pot_contribution(session: AsyncSession, user: m.User, group_id: str, amount_paise: int, note: str | None) -> m.GroupPotContribution:
    me = await _member_of(session, group_id, user.id)
    if amount_paise <= 0:
        raise CollabError("amount must be more than zero")
    c = m.GroupPotContribution(group_id=group_id, member_id=me.id, amount_paise=amount_paise, method="upi", note=(note or "")[:120] or None,
                               occurred_at=now_utc())
    session.add(c)
    await session.flush()
    return c


async def set_sharing(session: AsyncSession, user: m.User, group_id: str, sharing: dict[str, Any]) -> dict[str, Any]:
    me = await _member_of(session, group_id, user.id)
    me.sharing = {"category_ids": [str(c) for c in sharing.get("category_ids") or []][:40],
                  "show_transactions": bool(sharing.get("show_transactions")),
                  "goal_ids": [str(g) for g in sharing.get("goal_ids") or []][:20]}
    return me.sharing
