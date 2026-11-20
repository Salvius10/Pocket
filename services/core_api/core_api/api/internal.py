"""Internal endpoints: the agent's tools and the scheduled jobs. Guarded by the internal token.

Every tool result carries ready-to-speak `say` text built by code. Write tools only ever create
a proposal; nothing here executes a write for the mascot.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pocket_common.layout import CATALOG
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from core_api import models as m
from core_api.api.deps import InternalUser, Session, require_internal, resolve_token_user
from core_api.api.public import me_view, refresh
from core_api.collab import service as collab
from core_api.config import now_utc, today_ist
from core_api.home import service as home
from core_api.i18n import t
from core_api.insights import engine as insights
from core_api.ledger import summary
from core_api.ledger.context import Ctx, load_ctx
from core_api.nudges import planner as nudges
from core_api.proposals import service as proposals
from core_api.pulse import service as pulse

router = APIRouter(prefix="/internal", dependencies=[Depends(require_internal)])

WRITE_TOOLS = ("set_goal", "create_pocket", "move_between_pockets", "add_transaction")
TOOLS = ("get_summary", "get_transactions", "compare_spend", "check_affordability", "get_insights", "get_pulse", "get_groups",
         "save_profile", "compose_home", "show_widget", *WRITE_TOOLS)
PROFILE_KEYS = ("income", "income_amount", "saving_for", "worries", "occupation", "household")


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    args: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None


def rupees_to_paise(value: Any) -> int:
    """The model passes rupees as it heard them; code turns them into paise. Never the other way round."""
    try:
        d = Decimal(str(value).replace(",", "").replace("₹", "").strip())
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(422, "amount must be a number of rupees") from exc
    return int((d * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _amount(args: dict[str, Any], *names: str) -> int | None:
    for n in names:
        if args.get(f"{n}_paise") is not None:
            return int(args[f"{n}_paise"])
        if args.get(f"{n}_rupees") is not None:
            return rupees_to_paise(args[f"{n}_rupees"])
        if args.get(n) is not None:
            return rupees_to_paise(args[n])
    return None


def resolve_category(ctx: Ctx, text: Any) -> str | None:
    if not text:
        return None
    needle = str(text).strip().lower().replace(" ", "_")
    if needle in ctx.categories:
        return needle
    plain = needle.replace("_", " ")
    for c in ctx.categories.values():
        names = [c.id.replace("_", " "), c.name_en.lower(), c.name_hi.lower(), c.name_ta.lower()]
        if any(plain == n or (len(plain) >= 4 and (plain in n or n in plain)) for n in names if n):
            return c.id
    return None


def _say(parts: list[str]) -> str:
    return " ".join(p for p in parts if p)


async def run_tool(session: Session, user: m.User, name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name not in TOOLS:
        raise HTTPException(404, f"unknown tool: {name}")
    ctx = await load_ctx(session, user)
    lang = ctx.lang

    if name == "get_summary":
        sections = [s for s in (args.get("sections") or ["safe_to_spend"]) if s in summary.SECTIONS] or ["safe_to_spend"]
        result = summary.build_summary(ctx, sections)
        says = []
        for s in sections:
            sec = result[s]
            if isinstance(sec, dict):
                says.append(sec.get("say", ""))
            else:  # pockets / goals lists: speak the ones that matter most
                ranked = sorted(sec, key=lambda r: -r.get("pct", 0))[:3] if s == "pockets" else sec[:2]
                says.extend(r["say"] for r in ranked)
        return {"result": result, "say": _say(says)}

    if name == "get_transactions":
        f = args.get("filters") or args
        cat = resolve_category(ctx, f.get("category"))
        result = summary.find_transactions(
            ctx, q=f.get("query") or f.get("merchant") or (None if cat else f.get("category")), category=cat,
            direction=f.get("direction") if f.get("direction") in ("debit", "credit") else None, period=f.get("period") or "this_month",
            min_paise=_amount(f, "min"), max_paise=_amount(f, "max"), limit=min(int(f.get("limit") or 8), 20),
        )
        return {"result": result, "say": result["say"]}

    if name == "compare_spend":
        result = summary.compare_spend(ctx, resolve_category(ctx, args.get("category")), str(args.get("period_a") or "last_month_to_date"),
                                       str(args.get("period_b") or "this_month"))
        return {"result": result, "say": result["say"]}

    if name == "check_affordability":
        amount = _amount(args, "amount")
        if amount is None or amount <= 0:
            raise HTTPException(422, "amount is required")
        result = summary.check_affordability(ctx, amount)
        return {"result": result, "say": result["say"]}

    if name == "get_insights":
        every = await insights.list_insights(session, ctx)
        rows = every[:5]
        if not rows:
            return {"result": {"insights": []}, "say": t(lang, "insights.say_none")}
        # Lead with the most serious one, then the one that comes with something the user can do.
        actionable = next((r for r in every if r["proposal"]), None)
        spoken = [rows[0]["say"]]
        if actionable is not None and actionable is not rows[0]:
            spoken.append(actionable["say"])
        elif len(rows) > 1:
            spoken.append(rows[1]["say"])
        client = None
        if actionable is not None:
            client = {"type": "confirm_request", "proposal": actionable["proposal"]}
            spoken += [actionable["proposal"]["say"], t(lang, "proposal.ask_tap")]
        return {"result": {"insights": rows}, "say": _say(spoken), "client": client}

    if name == "get_pulse":
        result = await pulse.get_pulse(session, ctx)
        return {"result": result, "say": result["say"]}

    if name == "get_groups":
        groups = await collab.groups_overview(session, user)
        gid = args.get("group_id")
        if gid:
            groups = [g for g in groups if g["id"] == gid or g["name"].lower() == str(gid).lower()] or groups
        say = _say([g["say"] for g in groups]) if groups else t(lang, "groups.say_none")
        return {"result": {"groups": groups}, "say": say}

    if name == "save_profile":
        facts = args.get("facts") or {}
        if isinstance(facts, list):
            facts = {str(f.get("key")): f.get("value") for f in facts if isinstance(f, dict)}
        existing = {f.key: f for f in (await session.execute(select(m.ProfileFact).where(m.ProfileFact.user_id == user.id))).scalars()}
        for key, value in facts.items():
            if key not in PROFILE_KEYS or not value:
                continue
            row = existing.get(key)
            if row is None:
                session.add(m.ProfileFact(user_id=user.id, key=key, value=str(value)[:500], source="onboarding", language=lang))
            else:
                row.value = str(value)[:500]
        if user.onboarding_step in ("language", "voice", "talk"):
            user.onboarding_step = "persona"
        await session.commit()
        return {"result": {"saved": sorted(k for k in facts if k in PROFILE_KEYS)}, "say": t(lang, "profile.saved"),
                "client": {"type": "profile_saved"}}

    if name == "compose_home":
        layout, outcome = await home.compose(session, ctx, (str(args.get("instruction"))[:300] if args.get("instruction") else None))
        await session.commit()
        if outcome == "unchanged":  # never claim a change that did not happen
            return {"result": {"outcome": outcome, "changed": False}, "say": t(lang, "home.unchanged")}
        view = home.layout_view(layout)
        say = layout.spec.get("summary") or t(lang, "home.updated")
        return {"result": {"outcome": outcome, "widgets": [w["type"] for w in layout.spec["widgets"]], "reasons": layout.spec.get("reasons", [])},
                "say": say, "client": {"type": "home_updated", "home": view}}

    if name == "show_widget":
        wtype = str(args.get("type") or "")
        if wtype not in CATALOG:
            raise HTTPException(422, "unknown widget type")
        section = {"bills_emis": "bills", "insight_card": None, "pulse_card": None, "group_pot": None, "transactions": None}.get(wtype, wtype)
        say = ""
        if section:
            sec = summary.build_summary(ctx, [section])[section]
            say = sec.get("say", "") if isinstance(sec, dict) else _say([r["say"] for r in sec[:2]])
        return {"result": {"shown": wtype}, "say": say,
                "client": {"type": "show_widget", "widget": {"type": wtype, "variant": "default", "params": args.get("params") or {}}}}

    # ---- write tools: build a proposal, never execute ----
    payload = dict(args)
    if name == "move_between_pockets":
        payload = {"from": args.get("from") or args.get("from_pocket"), "to": args.get("to") or args.get("to_pocket") or args.get("to_goal"),
                   "from_pocket_id": args.get("from_pocket_id"), "to_pocket_id": args.get("to_pocket_id"), "to_goal_id": args.get("to_goal_id"),
                   "amount_paise": _amount(args, "amount")}
    elif name == "set_goal":
        payload = {"goal_id": args.get("goal_id"), "name": args.get("name"), "emoji": args.get("emoji"),
                   "target_paise": _amount(args, "target", "amount"), "deadline": args.get("deadline"),
                   "monthly_plan_paise": _amount(args, "monthly_plan", "monthly")}
    elif name == "create_pocket":
        cats = [c for c in (resolve_category(ctx, x) for x in (args.get("category_ids") or args.get("categories") or [args.get("name")])) if c]
        payload = {"name": args.get("name"), "emoji": args.get("emoji"), "monthly_limit_paise": _amount(args, "monthly_limit", "limit", "amount"),
                   "category_ids": cats}
    elif name == "add_transaction":
        payload = {"amount_paise": _amount(args, "amount"), "direction": args.get("direction") or "debit",
                   "category_id": resolve_category(ctx, args.get("category") or args.get("category_id")),
                   "description": args.get("description") or args.get("merchant") or "", "date": args.get("date")}
    try:
        prop = await proposals.create_proposal(session, ctx, name, {k: v for k, v in payload.items() if v is not None})
    except proposals.ProposalError as exc:
        await session.rollback()
        return {"result": {"created": False, "reason": str(exc)}, "say": "", "error": str(exc)}
    await session.commit()
    view = proposals.proposal_view(ctx, prop)
    return {"result": {"created": True, "proposal_id": prop.id, "needs_tap": True, "title": view["title"]},
            "say": _say([view["say"], t(lang, "proposal.ask_tap")]), "client": {"type": "confirm_request", "proposal": view}}


@router.post("/tools/{name}")
async def call_tool(name: str, body: ToolCall, session: Session, user: InternalUser) -> dict[str, Any]:
    out = await run_tool(session, user, name, body.args)
    if body.session_id:
        session.add(m.ChatTurn(session_id=body.session_id, user_id=user.id, role="tool", text="", tool_name=name))
        await session.commit()
    return {"ok": "error" not in out, "tool": name, **out}


# ---------- agent session plumbing ----------
class ResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str | None = None
    dev_user: str | None = None
    mode: str = "chat"


@router.post("/auth/resolve")
async def resolve(body: ResolveIn, session: Session) -> dict[str, Any]:
    """The phone's hello token -> user. Opens a chat session row for the transcript."""
    user = await resolve_token_user(session, body.token, body.dev_user)
    chat = m.ChatSession(user_id=user.id, mode=body.mode[:16], language=user.language)
    session.add(chat)
    await session.commit()
    ctx = await load_ctx(session, user)
    return {"user_id": user.id, "session_id": chat.id, "me": me_view(user, ctx.settings), "linked": user.persona_id is not None,
            "names": {"pockets": [p.name for p in ctx.pockets], "goals": [g.name for g in ctx.goals]}}


class TurnIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    role: str = Field(pattern="^(user|mascot)$")
    text: str = Field(max_length=4000)


@router.post("/chat/turn")
async def chat_turn(body: TurnIn, session: Session, user: InternalUser) -> dict[str, Any]:
    session.add(m.ChatTurn(session_id=body.session_id, user_id=user.id, role=body.role, text=body.text))
    await session.commit()
    return {"ok": True}


class GuardIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str | None = None
    kind: str = Field(pattern="^(number_mismatch|advice)$")
    detail: dict[str, Any] = Field(default_factory=dict)


@router.post("/guard/event")
async def guard_event(body: GuardIn, session: Session, user: InternalUser) -> dict[str, Any]:
    session.add(m.GuardEvent(user_id=user.id, session_id=body.session_id, kind=body.kind, detail=body.detail))
    await session.commit()
    return {"ok": True}


# ---------- jobs (Cloud Scheduler) ----------
class PulseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: date | None = None
    items: list[dict[str, Any]]


@router.post("/pulse/items")
async def put_pulse(body: PulseIn, session: Session) -> dict[str, Any]:
    kept = await pulse.replace_items(session, body.day or today_ist(), body.items)
    await session.commit()
    return {"kept": kept, "dropped": len(body.items) - kept}


async def _each_linked_user(session: Session) -> list[m.User]:
    return list((await session.execute(select(m.User).where(m.User.persona_id.is_not(None)))).scalars())


@router.post("/jobs/insights")
async def job_insights(session: Session) -> dict[str, Any]:
    users = await _each_linked_user(session)
    for u in users:
        await refresh(session, u)
    return {"users": len(users)}


@router.post("/jobs/nudges")
async def job_nudges(session: Session) -> dict[str, Any]:
    created = 0
    for u in await _each_linked_user(session):
        ctx = await load_ctx(session, u)
        created += len(await nudges.plan_nudges(session, ctx))
    await session.commit()
    return {"created": created}


@router.post("/jobs/nav")
async def job_nav(session: Session) -> dict[str, Any]:
    from core_api.market.amfi import ingest_latest

    return await ingest_latest(session)


class JobInject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str
    preset: str = "swiggy_now"


@router.post("/jobs/demo/inject")
async def job_inject(body: JobInject, session: Session) -> dict[str, Any]:
    from core_api.demo.inject import inject

    user = await session.get(m.User, body.user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    txn = await inject(session, await load_ctx(session, user), body.preset)
    await session.commit()
    await refresh(session, user)
    return {"transaction_id": txn.id, "at": now_utc().isoformat()}


_ = Annotated  # keep import for FastAPI typing helpers
