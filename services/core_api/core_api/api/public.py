"""Public REST API the app calls. Every amount is a Money object; the phone never does maths."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from core_api import models as m
from core_api.api.deps import CurrentUser, Session, UserCtx
from core_api.collab import service as collab
from core_api.config import now_utc
from core_api.home import service as home
from core_api.insights import engine as insights
from core_api.ledger import summary
from core_api.ledger.classify import spend_class
from core_api.ledger.context import Ctx, bump, load_ctx
from core_api.nudges import planner as nudges
from core_api.proposals import service as proposals
from core_api.pulse import service as pulse
from core_api.seed import loader

router = APIRouter(prefix="/v1")
DateT = date  # alias: models below have a field literally named `date`


class In(BaseModel):
    model_config = ConfigDict(extra="forbid")


def me_view(user: m.User, settings: m.UserSettings | None) -> dict[str, Any]:
    return {
        "id": user.id, "display_name": user.display_name, "first_name": user.first_name, "language": user.language,
        "mascot_voice": user.mascot_voice, "persona_id": user.persona_id, "income_pattern": user.income_pattern, "city": user.city,
        "occupation": user.occupation, "onboarding_step": user.onboarding_step,
        "settings": {"nudge_daily_max": settings.nudge_daily_max if settings else 2, "quiet_start": settings.quiet_start if settings else "22:00",
                     "quiet_end": settings.quiet_end if settings else "08:00", "mute_voice": settings.mute_voice if settings else False},
    }


async def refresh(session: Session, user: m.User) -> Ctx:
    """After a write: reload numbers, rerun insights, replan nudges."""
    ctx = await load_ctx(session, user)
    await insights.run_insights(session, ctx)
    await nudges.plan_nudges(session, ctx)
    await session.commit()
    return ctx


# ---------- me / settings / onboarding ----------
@router.get("/me")
async def get_me(session: Session, user: CurrentUser) -> dict[str, Any]:
    return me_view(user, await session.get(m.UserSettings, user.id))


class MePatch(In):
    language: Literal["en", "hi", "ta"] | None = None
    mascot_voice: str | None = Field(default=None, max_length=40)
    onboarding_step: Literal["language", "voice", "talk", "persona", "done"] | None = None


@router.patch("/me")
async def patch_me(body: MePatch, session: Session, user: CurrentUser) -> dict[str, Any]:
    if body.language:
        user.language = body.language
    if body.mascot_voice:
        user.mascot_voice = body.mascot_voice
    if body.onboarding_step:
        user.onboarding_step = body.onboarding_step
    await session.commit()
    return me_view(user, await session.get(m.UserSettings, user.id))


class SettingsIn(In):
    nudge_daily_max: int | None = Field(default=None, ge=0, le=2)
    quiet_start: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    quiet_end: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    mute_voice: bool | None = None


@router.put("/settings")
async def put_settings(body: SettingsIn, session: Session, user: CurrentUser) -> dict[str, Any]:
    s = await session.get(m.UserSettings, user.id)
    if s is None:
        s = m.UserSettings(user_id=user.id)
        session.add(s)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    await session.commit()
    return me_view(user, s)


@router.get("/onboarding/personas")
async def personas() -> dict[str, Any]:
    return {"personas": loader.persona_cards()}


class LinkIn(In):
    persona_id: Literal["student", "first_job", "family", "gig", "shop", "investor"]
    keep_language: bool = True


@router.post("/onboarding/link")
async def link(body: LinkIn, session: Session, user: CurrentUser) -> dict[str, Any]:
    counts = await loader.link_persona(session, user, body.persona_id)
    if not body.keep_language:
        user.language = str(loader.demo_data().users[body.persona_id]["language"])
    user.onboarding_step = "done"
    await session.commit()
    ctx = await refresh(session, user)
    if await keep_current(session, ctx):
        ctx = await refresh(session, user)
    # Build this person's Home now: the composer sees their features and what they told the mascot.
    # If it cannot answer, compose() leaves the persona's default layout in place.
    layout, outcome = await home.compose(session, ctx, None)
    await session.commit()
    return {"linked": counts, "me": me_view(user, ctx.settings), "home": home.layout_view(layout), "home_outcome": outcome}


async def keep_current(session: Session, ctx: Ctx) -> bool:
    """Demo data only: add the days between the dataset's last day and yesterday (the synthetic
    drip). Cheap when there is nothing to add. True if transactions were created."""
    from core_api.demo import drip
    from core_api.insights.engine import load_merchants

    created = await drip.catch_up(session, ctx, await load_merchants(session), loader.data_end())
    await session.commit()
    return created > 0


# ---------- the bundle the app caches ----------
@router.get("/sync")
async def sync(session: Session, ctx: UserCtx, since: str | None = None) -> dict[str, Any]:
    user = ctx.user
    if user.persona_id is not None and await keep_current(session, ctx):
        ctx = await refresh(session, user)  # a new day's transactions arrived: redo insights and nudges
    cursor = f"{user.data_version}:{ctx.today.isoformat()}:{user.language}"
    if user.persona_id is None:
        return {"changed": True, "cursor": cursor, "as_of": now_utc().isoformat(), "me": me_view(user, ctx.settings), "linked": False}
    layout = await home.current_layout(session, ctx)
    payload = {
        "changed": True, "cursor": cursor, "as_of": now_utc().isoformat(), "linked": True, "me": me_view(user, ctx.settings),
        "summary": summary.build_summary(ctx), "home": home.layout_view(layout),
        "insights": await insights.list_insights(session, ctx), "pulse": await pulse.get_pulse(session, ctx),
        "groups": await collab.groups_overview(session, user), "nudges": await nudges.due_nudges(session, ctx),
        "proposals": await proposals.list_pending(session, ctx),
        "transactions": summary.find_transactions(ctx, limit=40)["items"],
        "accounts": accounts_view(ctx),
        "categories": [{"id": c.id, "name": getattr(c, f"name_{ctx.lang}") or c.name_en, "emoji": c.emoji, "kind": c.kind}
                       for c in ctx.categories.values()],
    }
    await session.commit()
    return payload


@router.get("/summary")
async def get_summary(ctx: UserCtx, sections: str | None = None) -> dict[str, Any]:
    return summary.build_summary(ctx, sections.split(",") if sections else None)


# ---------- money ----------
def accounts_view(ctx: Ctx) -> list[dict[str, Any]]:
    out = []
    for a in ctx.accounts:
        row: dict[str, Any] = {"id": a.id, "institution": a.institution, "code": a.institution_code, "type": a.type,
                               "masked_number": a.masked_number, "last4": a.masked_number[-4:], "nickname": a.nickname,
                               "balance": summary.M(ctx, a.balance_paise),
                               "as_of": a.balance_as_of.isoformat() if a.balance_as_of else None}
        if a.type == "credit_card":
            row["credit_limit"] = summary.M(ctx, a.credit_limit_paise or 0)
            row["used_pct"] = min(100, (a.balance_paise * 100) // a.credit_limit_paise) if a.credit_limit_paise else 0
            row["due_day"] = a.due_day
        out.append(row)
    return out


@router.get("/accounts")
async def get_accounts(ctx: UserCtx) -> dict[str, Any]:
    return {"accounts": accounts_view(ctx)}


@router.get("/transactions")
async def get_transactions(
    ctx: UserCtx, q: str | None = None, category: str | None = None, direction: Literal["debit", "credit"] | None = None,
    period: str | None = None, date_from: date | None = None, date_to: date | None = None, account_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    return summary.find_transactions(ctx, q=q, category=category, direction=direction, period=period, date_from=date_from,
                                     date_to=date_to, account_id=account_id, limit=limit, offset=offset)


class TxnIn(In):
    amount_paise: int = Field(gt=0, le=10_00_00_000_00)
    direction: Literal["debit", "credit"] = "debit"
    category_id: str | None = None
    description: str = Field(default="", max_length=120)
    date: DateT | None = None


@router.post("/transactions")
async def add_transaction(body: TxnIn, session: Session, ctx: UserCtx) -> dict[str, Any]:
    """Manual cash entry typed by the user on the Money tab (a tap, so it executes directly)."""
    try:
        payload = proposals.normalise(ctx, "add_transaction", {**body.model_dump(exclude_none=True),
                                                               "date": body.date.isoformat() if body.date else None})
    except proposals.ProposalError as exc:
        raise HTTPException(422, str(exc)) from exc
    txn = await proposals.add_manual_transaction(session, ctx, payload)
    session.add(m.AuditLog(user_id=ctx.user.id, action="transaction.add", entity="transaction", entity_id=txn.id, detail=payload))
    await bump(session, ctx.user)
    await session.commit()
    new_ctx = await refresh(session, ctx.user)
    return {"transaction": summary.txn_row(new_ctx, next(x for x in new_ctx.txns if x.id == txn.id))}


class TxnPatch(In):
    category_id: str | None = None
    hidden: bool | None = None
    note: str | None = Field(default=None, max_length=200)


@router.patch("/transactions/{txn_id}")
async def patch_transaction(txn_id: str, body: TxnPatch, session: Session, ctx: UserCtx) -> dict[str, Any]:
    txn = await session.get(m.Transaction, txn_id)
    if txn is None or txn.user_id != ctx.user.id:
        raise HTTPException(404, "transaction not found")
    if body.category_id is not None:
        if body.category_id not in ctx.categories:
            raise HTTPException(422, "unknown category")
        txn.category = body.category_id
    if body.hidden is not None:
        txn.hidden = body.hidden
    if body.note is not None:
        txn.note = body.note
    cat = ctx.categories[txn.category]
    rec = next((r for r in ctx.recurring if r.id == txn.recurring_item_id), None)
    txn.spend_class = spend_class(status=txn.status, hidden=txn.hidden, is_reversal=txn.reversal_of_id is not None,
                                  category_kind=cat.kind, category_default_class=cat.default_class, recurring_kind=rec.kind if rec else None)
    session.add(m.AuditLog(user_id=ctx.user.id, action="transaction.edit", entity="transaction", entity_id=txn.id,
                           detail=body.model_dump(exclude_none=True)))
    await bump(session, ctx.user)
    await session.commit()
    new_ctx = await refresh(session, ctx.user)
    return {"transaction": summary.txn_row(new_ctx, next(x for x in new_ctx.txns if x.id == txn_id))}


@router.get("/recurring")
async def get_recurring(ctx: UserCtx) -> dict[str, Any]:
    items = []
    for r in ctx.recurring:
        nd = ctx.next_due.get(r.id)
        items.append({"id": r.id, "name": r.name, "kind": r.kind, "category_id": r.category, "cadence": r.cadence,
                      "amount": summary.M(ctx, r.amount_paise), "variable": r.amount_is_variable, "status": r.status,
                      "next_due": nd.isoformat() if nd else None, "autopay": (r.channel or "") in ("ach", "autopay", "card")})
    return {"recurring": sorted(items, key=lambda x: (x["next_due"] is None, x["next_due"] or "", x["name"])), "bills": summary.bills(ctx, 30)}


@router.get("/loans")
async def get_loans(ctx: UserCtx) -> dict[str, Any]:
    return {"loans": [
        {"id": ln.id, "lender": ln.lender, "loan_type": ln.loan_type, "rate_type": ln.rate_type, "rate_bps": ln.interest_rate_bps,
         "principal": summary.M(ctx, ln.principal_paise), "outstanding": summary.M(ctx, ln.outstanding_paise), "emi": summary.M(ctx, ln.emi_paise),
         "emi_day": ln.emi_day, "months_left": ln.months_left, "emis_paid": ln.emis_paid, "tenure_months": ln.tenure_months,
         "paid_pct": min(100, (ln.emis_paid * 100) // ln.tenure_months) if ln.tenure_months else 0, "zero_cost": ln.zero_cost_emi,
         "end_date": ln.end_date.isoformat() if ln.end_date else None}
        for ln in ctx.loans
    ]}


@router.get("/investments")
async def get_investments(ctx: UserCtx) -> dict[str, Any]:
    return summary.investments(ctx)


# ---------- plan ----------
class PocketIn(In):
    name: str = Field(min_length=1, max_length=80)
    emoji: str = Field(default="👛", max_length=8)
    monthly_limit_paise: int = Field(gt=0, le=10_00_00_000_00)
    category_ids: list[str] = Field(min_length=1)


@router.post("/pockets")
async def create_pocket(body: PocketIn, session: Session, ctx: UserCtx) -> dict[str, Any]:
    try:
        payload = proposals.normalise(ctx, "create_pocket", body.model_dump())
    except proposals.ProposalError as exc:
        raise HTTPException(422, str(exc)) from exc
    pocket = m.Pocket(user_id=ctx.user.id, sort_order=len(ctx.pockets), created_by="user", **payload)
    session.add(pocket)
    await bump(session, ctx.user)
    await session.commit()
    await refresh(session, ctx.user)
    return {"id": pocket.id}


class PocketPatch(In):
    status: Literal["active", "paused", "archived"] | None = None
    monthly_limit_paise: int | None = Field(default=None, gt=0, le=10_00_00_000_00)


@router.patch("/pockets/{pocket_id}")
async def patch_pocket(pocket_id: str, body: PocketPatch, session: Session, ctx: UserCtx) -> dict[str, Any]:
    pocket = await session.get(m.Pocket, pocket_id)
    if pocket is None or pocket.user_id != ctx.user.id:
        raise HTTPException(404, "pocket not found")
    if body.status:
        pocket.status = body.status
    if body.monthly_limit_paise:
        pocket.monthly_limit_paise = body.monthly_limit_paise
    await bump(session, ctx.user)
    await session.commit()
    await refresh(session, ctx.user)
    return {"ok": True}


class GoalIn(In):
    name: str = Field(min_length=1, max_length=80)
    emoji: str = Field(default="🎯", max_length=8)
    target_paise: int = Field(gt=0, le=10_00_00_000_00)
    deadline: date | None = None
    monthly_plan_paise: int | None = Field(default=None, gt=0)


@router.post("/goals")
async def create_goal(body: GoalIn, session: Session, ctx: UserCtx) -> dict[str, Any]:
    if body.deadline is not None and body.deadline <= ctx.today:
        raise HTTPException(422, "deadline must be in the future")
    goal = m.Goal(user_id=ctx.user.id, created_by="user", priority=0, **body.model_dump())
    session.add(goal)
    await bump(session, ctx.user)
    await session.commit()
    await refresh(session, ctx.user)
    return {"id": goal.id}


@router.get("/proposals")
async def get_proposals(session: Session, ctx: UserCtx) -> dict[str, Any]:
    out = await proposals.list_pending(session, ctx)
    await session.commit()
    return {"proposals": out}


@router.post("/proposals/{proposal_id}/accept")
async def accept(proposal_id: str, session: Session, ctx: UserCtx) -> dict[str, Any]:
    """The only way a mascot-suggested write runs: a tap on the confirm card."""
    try:
        p = await proposals.accept_proposal(session, ctx, proposal_id)
        await session.commit()
    except proposals.ProposalError as exc:
        await session.rollback()
        raise HTTPException(409, str(exc)) from exc
    new_ctx = await refresh(session, ctx.user)
    return {"id": p.id, "status": p.status, "summary": summary.build_summary(new_ctx)}


@router.post("/proposals/{proposal_id}/decline")
async def decline(proposal_id: str, session: Session, user: CurrentUser) -> dict[str, Any]:
    try:
        p = await proposals.decline_proposal(session, user, proposal_id)
    except proposals.ProposalError as exc:
        raise HTTPException(404, str(exc)) from exc
    await session.commit()
    return {"id": p.id, "status": p.status}


# ---------- insights / pulse / nudges ----------
@router.get("/insights")
async def get_insights(session: Session, ctx: UserCtx) -> dict[str, Any]:
    return {"insights": await insights.list_insights(session, ctx)}


@router.post("/insights/{insight_id}/dismiss")
async def dismiss_insight(insight_id: str, session: Session, user: CurrentUser) -> dict[str, Any]:
    row = await session.get(m.Insight, insight_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "insight not found")
    row.status = "dismissed"
    await session.commit()
    return {"ok": True}


@router.get("/pulse")
async def get_pulse(session: Session, ctx: UserCtx) -> dict[str, Any]:
    return await pulse.get_pulse(session, ctx)


@router.get("/nudges")
async def get_nudges(session: Session, ctx: UserCtx) -> dict[str, Any]:
    out = await nudges.due_nudges(session, ctx)
    await session.commit()
    return {"nudges": out}


@router.post("/nudges/{nudge_id}/dismiss")
async def dismiss_nudge(nudge_id: str, session: Session, user: CurrentUser) -> dict[str, Any]:
    row = await session.get(m.Nudge, nudge_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "nudge not found")
    row.status = "dismissed"
    await session.commit()
    return {"ok": True}


@router.get("/reports/monthly")
async def monthly_report(ctx: UserCtx, month: str | None = None) -> dict[str, Any]:
    """The monthly report screen: every figure and every sentence is computed in code."""
    from core_api.reports.monthly import MONTH_KEY
    from core_api.reports.monthly import monthly_report as build

    if month is not None and not MONTH_KEY.match(month):
        raise HTTPException(422, "month must look like 2026-10")
    return build(ctx, month)


# ---------- home ----------
@router.get("/home")
async def get_home(session: Session, ctx: UserCtx) -> dict[str, Any]:
    row = await home.current_layout(session, ctx)
    await session.commit()
    return home.layout_view(row)


class ComposeIn(In):
    instruction: str | None = Field(default=None, max_length=300)


@router.post("/home/compose")
async def compose_home(body: ComposeIn, session: Session, ctx: UserCtx) -> dict[str, Any]:
    row, outcome = await home.compose(session, ctx, body.instruction)
    await session.commit()
    return {**home.layout_view(row), "outcome": outcome}


class ManualIn(In):
    widgets: list[dict[str, Any]] = Field(min_length=1, max_length=12)


@router.put("/home/manual")
async def manual_home(body: ManualIn, session: Session, ctx: UserCtx) -> dict[str, Any]:
    row = await home.manual(session, ctx, body.widgets)
    await session.commit()
    return home.layout_view(row)


@router.post("/home/reset")
async def reset_home(session: Session, ctx: UserCtx) -> dict[str, Any]:
    row = await home.store_layout(session, ctx.user, home.default_layout(ctx, await home.layout_context(session, ctx)), "default")
    await session.commit()
    return home.layout_view(row)


# ---------- collab ----------
def _collab(exc: collab.CollabError) -> HTTPException:
    return HTTPException(404 if "not found" in str(exc) else 422, str(exc))


@router.get("/groups")
async def get_groups(session: Session, user: CurrentUser) -> dict[str, Any]:
    return {"groups": await collab.groups_overview(session, user)}


class GroupIn(In):
    name: str = Field(min_length=1, max_length=80)
    type: Literal["family", "trip", "flatmates", "custom"]
    emoji: str = Field(default="", max_length=24)
    budget_monthly_paise: int | None = Field(default=None, gt=0)
    pot_target_paise: int | None = Field(default=None, gt=0)
    pot_deadline: date | None = None


@router.post("/groups")
async def create_group(body: GroupIn, session: Session, user: CurrentUser) -> dict[str, Any]:
    try:
        g = await collab.create_group(session, user, name=body.name, type_=body.type, emoji=body.emoji,
                                      budget_monthly_paise=body.budget_monthly_paise, pot_target_paise=body.pot_target_paise,
                                      pot_deadline=body.pot_deadline)
    except collab.CollabError as exc:
        raise _collab(exc) from exc
    await session.commit()
    return await collab.group_detail(session, user, g.id)


class JoinIn(In):
    code: str = Field(min_length=6, max_length=8)


@router.post("/groups/join")
async def join_group(body: JoinIn, session: Session, user: CurrentUser) -> dict[str, Any]:
    try:
        g = await collab.join_group(session, user, body.code)
    except collab.CollabError as exc:
        raise _collab(exc) from exc
    await session.commit()
    return await collab.group_detail(session, user, g.id)


@router.get("/groups/{group_id}")
async def get_group(group_id: str, session: Session, user: CurrentUser) -> dict[str, Any]:
    try:
        return await collab.group_detail(session, user, group_id)
    except collab.CollabError as exc:
        raise _collab(exc) from exc


class GuestIn(In):
    name: str = Field(min_length=1, max_length=80)
    vpa: str | None = Field(default=None, max_length=120)


@router.post("/groups/{group_id}/guests")
async def add_guest(group_id: str, body: GuestIn, session: Session, user: CurrentUser) -> dict[str, Any]:
    try:
        await collab.add_guest(session, user, group_id, body.name, body.vpa)
        await session.commit()
        return await collab.group_detail(session, user, group_id)
    except collab.CollabError as exc:
        raise _collab(exc) from exc


class ExpenseIn(In):
    amount_paise: int = Field(gt=0, le=10_00_00_000_00)
    description: str = Field(default="", max_length=200)
    paid_by_member_id: str | None = None
    split_method: Literal["equal", "percent", "exact"] = "equal"
    split_input: dict[str, Any] = Field(default_factory=dict)
    category_id: str | None = None
    linked_transaction_id: str | None = None


@router.post("/groups/{group_id}/expenses")
async def add_expense(group_id: str, body: ExpenseIn, session: Session, user: CurrentUser) -> dict[str, Any]:
    try:
        await collab.add_expense(session, user, group_id, amount_paise=body.amount_paise, description=body.description,
                                 paid_by_member_id=body.paid_by_member_id, split_method=body.split_method, split_input=body.split_input,
                                 category=body.category_id, linked_transaction_id=body.linked_transaction_id)
        await session.commit()
    except collab.CollabError as exc:
        await session.rollback()
        raise _collab(exc) from exc
    if body.linked_transaction_id:
        await refresh(session, user)
    return await collab.group_detail(session, user, group_id)


@router.delete("/groups/{group_id}/expenses/{expense_id}")
async def delete_expense(group_id: str, expense_id: str, session: Session, user: CurrentUser) -> dict[str, Any]:
    try:
        await collab.delete_expense(session, user, group_id, expense_id)
        await session.commit()
        return await collab.group_detail(session, user, group_id)
    except collab.CollabError as exc:
        raise _collab(exc) from exc


class SettleIn(In):
    from_member_id: str
    to_member_id: str
    amount_paise: int = Field(gt=0, le=10_00_00_000_00)


@router.post("/groups/{group_id}/settlements")
async def create_settlement(group_id: str, body: SettleIn, session: Session, user: CurrentUser) -> dict[str, Any]:
    try:
        s = await collab.create_settlement(session, user, group_id, from_member_id=body.from_member_id, to_member_id=body.to_member_id,
                                           amount_paise=body.amount_paise)
        await session.commit()
    except collab.CollabError as exc:
        raise _collab(exc) from exc
    detail = await collab.group_detail(session, user, group_id)
    return {"settlement_id": s.id, "upi_link": s.upi_link, "group": detail}


class SettleStatusIn(In):
    status: Literal["link_opened", "marked_paid", "confirmed"]


@router.post("/groups/{group_id}/settlements/{settlement_id}/status")
async def settlement_status(group_id: str, settlement_id: str, body: SettleStatusIn, session: Session, user: CurrentUser) -> dict[str, Any]:
    try:
        await collab.set_settlement_status(session, user, group_id, settlement_id, body.status)
        await session.commit()
        return await collab.group_detail(session, user, group_id)
    except collab.CollabError as exc:
        raise _collab(exc) from exc


class PotIn(In):
    amount_paise: int = Field(gt=0, le=10_00_00_000_00)
    note: str | None = Field(default=None, max_length=120)


@router.post("/groups/{group_id}/pot")
async def pot_contribution(group_id: str, body: PotIn, session: Session, user: CurrentUser) -> dict[str, Any]:
    try:
        await collab.add_pot_contribution(session, user, group_id, body.amount_paise, body.note)
        await session.commit()
        return await collab.group_detail(session, user, group_id)
    except collab.CollabError as exc:
        raise _collab(exc) from exc


class SharingIn(In):
    category_ids: list[str] = Field(default_factory=list)
    show_transactions: bool = False
    goal_ids: list[str] = Field(default_factory=list)


@router.put("/groups/{group_id}/sharing")
async def put_sharing(group_id: str, body: SharingIn, session: Session, user: CurrentUser) -> dict[str, Any]:
    try:
        out = await collab.set_sharing(session, user, group_id, body.model_dump())
        await session.commit()
        return {"sharing": out}
    except collab.CollabError as exc:
        raise _collab(exc) from exc


# ---------- privacy ----------
@router.get("/export")
async def export(session: Session, ctx: UserCtx) -> dict[str, Any]:
    facts = (await session.execute(select(m.ProfileFact).where(m.ProfileFact.user_id == ctx.user.id))).scalars()
    return {"exported_at": now_utc().isoformat(), "me": me_view(ctx.user, ctx.settings),
            "profile_facts": [{"key": f.key, "value": f.value} for f in facts], "summary": summary.build_summary(ctx),
            "accounts": accounts_view(ctx), "transactions": summary.find_transactions(ctx, limit=200)["items"]}


@router.delete("/me")
async def delete_me(session: Session, user: CurrentUser) -> dict[str, Any]:
    """Delete everything about this user. The row itself goes too."""
    from core_api.ledger.context import _ctx_cache

    await loader.wipe_user_data(session, user.id)
    settings = await session.get(m.UserSettings, user.id)
    if settings is not None:
        await session.delete(settings)
    await session.delete(user)
    await session.commit()
    _ctx_cache.pop(user.id, None)
    return {"deleted": True}


# ---------- demo tools ----------
class InjectIn(In):
    preset: Literal["swiggy_now", "salary_now", "chai_now"] = "swiggy_now"


@router.post("/demo/inject")
async def demo_inject(body: InjectIn, session: Session, ctx: UserCtx) -> dict[str, Any]:
    from core_api.demo.inject import inject

    result = await inject(session, ctx, body.preset)
    txn_id, sms = result.transaction.id if result.transaction else "", {"sender_id": result.sms.sender_id, "body": result.sms.body}
    await session.commit()
    new_ctx = await refresh(session, ctx.user)
    return {"transaction": summary.txn_row(new_ctx, next(x for x in new_ctx.txns if x.id == txn_id)),
            "sms": sms,  # the synthetic bank SMS this transaction was read from
            "nudges": await nudges.due_nudges(session, new_ctx)}
