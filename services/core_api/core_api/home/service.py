"""Home layouts: versioned LayoutSpec + A2UI messages. core-api stores and validates; the agent composes."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import httpx
from pocket_common.a2ui import build_messages
from pocket_common.layout import (
    CATALOG,
    LayoutContext,
    LayoutSpec,
    Reason,
    WidgetSpec,
    enforce_layout,
    has_digit,
    validate_layout,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core_api import models as m
from core_api.config import get_settings
from core_api.ledger.context import Ctx

DEFAULT_REASONS = {
    "en": "Safe-to-spend always comes first.",
    "hi": "आज कितना खर्च कर सकते हैं, यह हमेशा सबसे ऊपर रहता है।",
    "ta": "இன்று எவ்வளவு செலவழிக்கலாம் என்பது எப்போதும் முதலில்.",
}


@lru_cache
def _ideal_layouts() -> dict[str, dict[str, Any]]:
    path = get_settings().data_path / "content" / "ideal_layouts.json"
    return {row["persona_id"]: row for row in json.loads(path.read_text(encoding="utf-8"))}


async def user_group_ids(session: AsyncSession, user_id: str) -> list[str]:
    return list((await session.execute(
        select(m.GroupMember.group_id).where(m.GroupMember.user_id == user_id).order_by(m.GroupMember.group_id)
    )).scalars())


async def layout_context(session: AsyncSession, ctx: Ctx) -> LayoutContext:
    """Which widgets this user has data for."""
    groups = await user_group_ids(session, ctx.user.id)
    has_insight = (await session.execute(
        select(m.Insight.id).where(m.Insight.user_id == ctx.user.id, m.Insight.status == "active").limit(1)
    )).first() is not None
    available = {"safe_to_spend", "spend_by_category", "cash_flow", "transactions", "pulse_card"}
    if ctx.pockets:
        available.add("pockets")
    if ctx.goals:
        available.add("goals")
    if any(r.kind in ("rent", "emi", "bill", "subscription", "insurance", "sip") for r in ctx.recurring) or ctx.loans:
        available.add("bills_emis")
    if ctx.accounts:
        available.add("net_worth")
    if ctx.holdings:
        available.add("investments")
    if has_insight:
        available.add("insight_card")
    if groups:
        available.add("group_pot")
    return LayoutContext(available=available, group_ids=set(groups), goal_ids={g.id for g in ctx.goals},
                         default_group_id=groups[0] if groups else None)


def default_layout(ctx: Ctx, lctx: LayoutContext) -> LayoutSpec:
    """The fixed default for the persona (data/content/ideal_layouts.json), fitted to this user's data."""
    ideal = _ideal_layouts().get(ctx.user.persona_id or "")
    if ideal is not None:
        spec = LayoutSpec.model_validate(ideal["spec"])
        for w in spec.widgets:
            if w.type == "group_pot":
                w.params["group_id"] = lctx.default_group_id
        if ideal.get("language") != ctx.lang:
            spec = LayoutSpec(widgets=spec.widgets, reasons=[Reason(widget_index=0, text=DEFAULT_REASONS.get(ctx.lang, DEFAULT_REASONS["en"]))], summary="")
    else:
        spec = LayoutSpec(widgets=[WidgetSpec(type=t) for t in ("safe_to_spend", "pockets", "insight_card", "goals", "spend_by_category", "transactions")])
    return enforce_layout(spec, lctx)


async def store_layout(session: AsyncSession, user: m.User, spec: LayoutSpec, source: str, instruction: str | None = None) -> m.HomeLayout:
    last = (await session.execute(
        select(m.HomeLayout.version).where(m.HomeLayout.user_id == user.id).order_by(m.HomeLayout.version.desc()).limit(1)
    )).scalar()
    await session.execute(update(m.HomeLayout).where(m.HomeLayout.user_id == user.id, m.HomeLayout.is_current.is_(True)).values(is_current=False))
    row = m.HomeLayout(user_id=user.id, version=(last or 0) + 1, is_current=True, source=source, spec=spec.model_dump(),
                       a2ui=build_messages(spec), instruction=(instruction or None))
    session.add(row)
    await session.flush()
    return row


def layout_view(row: m.HomeLayout) -> dict[str, Any]:
    return {"version": row.version, "source": row.source, "spec": row.spec, "a2ui": row.a2ui, "instruction": row.instruction,
            "created_at": row.created_at.isoformat() if row.created_at else None}


async def current_layout(session: AsyncSession, ctx: Ctx) -> m.HomeLayout:
    row = (await session.execute(
        select(m.HomeLayout).where(m.HomeLayout.user_id == ctx.user.id, m.HomeLayout.is_current.is_(True)).limit(1)
    )).scalars().first()
    if row is None:
        row = await store_layout(session, ctx.user, default_layout(ctx, await layout_context(session, ctx)), "default")
    return row


async def composer_features(session: AsyncSession, ctx: Ctx) -> dict[str, Any]:
    """What the composer may see: features and names, never amounts."""
    insights = list((await session.execute(
        select(m.Insight.type).where(m.Insight.user_id == ctx.user.id, m.Insight.status == "active")
        .order_by(m.Insight.severity.desc(), m.Insight.impact_paise.desc()).limit(5)
    )).scalars())
    facts = {f.key: f.value for f in (await session.execute(select(m.ProfileFact).where(m.ProfileFact.user_id == ctx.user.id))).scalars()
             if f.key in ("saving_for", "worries", "occupation", "household") and not has_digit(f.value)}
    groups = [{"id": g.id, "name": g.name, "type": g.type, "has_pot": g.pot_target_paise is not None}
              for gid in await user_group_ids(session, ctx.user.id) if (g := await session.get(m.Group, gid)) is not None]
    return {
        "language": ctx.lang, "persona": ctx.user.persona_id, "income_pattern": ctx.user.income_pattern,
        "has_emis": any(r.kind == "emi" and r.status == "active" for r in ctx.recurring), "has_loans": bool(ctx.loans),
        "has_goals": bool(ctx.goals), "goal_names": [g.name for g in ctx.goals], "pocket_names": [p.name for p in ctx.pockets],
        "has_investments": bool(ctx.holdings), "has_credit_card": any(a.type == "credit_card" for a in ctx.accounts),
        "top_insight_types": insights, "groups": groups, "profile": facts,
    }


async def compose(session: AsyncSession, ctx: Ctx, instruction: str | None) -> tuple[m.HomeLayout, str]:
    """Ask the agent for a layout, validate it here, and store it. Returns (layout, outcome)."""
    lctx = await layout_context(session, ctx)
    current = await current_layout(session, ctx)
    settings = get_settings()
    body = {
        "features": await composer_features(session, ctx), "instruction": instruction, "current": current.spec,
        "default": default_layout(ctx, lctx).model_dump(),
        "context": {"available": sorted(lctx.available), "group_ids": sorted(lctx.group_ids), "goal_ids": sorted(lctx.goal_ids),
                    "default_group_id": lctx.default_group_id},
    }
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            r = await client.post(f"{settings.agent_url}/v1/compose", json=body, headers={"X-Internal-Token": settings.internal_token})
            r.raise_for_status()
            answer = r.json()
            spec = LayoutSpec.model_validate(answer["spec"])
            outcome = str(answer.get("outcome") or "composer")  # composer | repaired | rules | fake | default
    except (httpx.HTTPError, KeyError, ValueError):
        # The agent could not be reached or answered nonsense. Keep the Home the user already has.
        return current, "unchanged"
    if validate_layout(spec, lctx):
        spec, outcome = default_layout(ctx, lctx), "default"
    row = await store_layout(session, ctx.user, spec, outcome[:12], instruction)
    return row, outcome


async def manual(session: AsyncSession, ctx: Ctx, widgets: list[dict[str, Any]]) -> m.HomeLayout:
    """Long-press reorder/hide. Safe-to-spend stays pinned first whatever the phone sends."""
    lctx = await layout_context(session, ctx)
    spec = LayoutSpec(widgets=[WidgetSpec.model_validate(w) for w in widgets if w.get("type") in CATALOG])
    return await store_layout(session, ctx.user, enforce_layout(spec, lctx), "manual")
