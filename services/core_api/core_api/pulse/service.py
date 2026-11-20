"""Pulse: the agent writes the news items (with sources); code works out what each means for a user."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pocket_common.money import money
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api import models as m
from core_api.config import today_ist
from core_api.i18n import t
from core_api.ledger import mathx, summary
from core_api.ledger.context import Ctx

TAGS = ("mutual_funds", "rates", "fuel", "groceries", "gold", "fd", "general")


async def replace_items(session: AsyncSession, day: date, items: list[dict[str, Any]]) -> int:
    """Store the day's items. Anything without a source URL is dropped."""
    await session.execute(delete(m.PulseItem).where(m.PulseItem.day == day))
    kept = 0
    for rank, it in enumerate(items[:8]):
        url = str(it.get("source_url") or "")
        if not url.startswith(("http://", "https://")):
            continue
        session.add(m.PulseItem(
            day=day, topic=str(it.get("topic") or "markets")[:24], title=dict(it.get("title") or {}), summary=dict(it.get("summary") or {}),
            source_name=str(it.get("source_name") or "")[:120], source_url=url[:600],
            tags=[x for x in (it.get("tags") or []) if x in TAGS], rank=rank,
        ))
        kept += 1
    await session.flush()
    return kept


def personal_lines(ctx: Ctx, tags: list[str]) -> list[str]:
    """'What it means for you': every number here is computed by code from the user's ledger."""
    lang = ctx.lang
    lines: list[str] = []

    def spoken(p: int) -> str:
        return money(p, lang)["display"]

    if "mutual_funds" in tags:
        inv = summary.investments(ctx)
        if inv["mutual_funds"]["paise"] > 0:
            lines.append(t(lang, "pulse.link.mf_week", dir=t(lang, f"dir.{inv['week_direction']}"), amt=spoken(abs(inv["week_change"]["paise"]))))
        if inv["nifty_week_bps"] is not None:
            pct = (Decimal(inv["nifty_week_bps"]) / 100).quantize(Decimal("0.1"))
            lines.append(t(lang, "pulse.link.nifty", pct=f"{pct:+}"))
    if "rates" in tags:
        for ln in ctx.loans:
            if ln.rate_type == "floating" and ln.outstanding_paise > 0 and ln.months_left > 0:
                change = mathx.emi_change_for_rate_move(ln.outstanding_paise, ln.interest_rate_bps, ln.months_left, 25)
                lines.append(t(lang, "pulse.link.rate_move", lender=ln.lender, amt=spoken(abs(change))))
        fd = sum(int(h.fd_principal_paise or 0) for h in ctx.holdings if h.kind == "fd")
        if fd > 0:
            lines.append(t(lang, "pulse.link.fd", amt=spoken(fd)))
    if "fd" in tags and "rates" not in tags:
        fd = sum(int(h.fd_principal_paise or 0) for h in ctx.holdings if h.kind == "fd")
        if fd > 0:
            lines.append(t(lang, "pulse.link.fd", amt=spoken(fd)))
    totals = summary.category_totals(ctx, ctx.month)
    if "fuel" in tags and totals.get("fuel", 0) > 0:
        lines.append(t(lang, "pulse.link.fuel", amt=spoken(totals["fuel"])))
    if "groceries" in tags and totals.get("groceries", 0) > 0:
        lines.append(t(lang, "pulse.link.groceries", amt=spoken(totals["groceries"])))
    if "gold" in tags:
        grams = sum((Decimal(h.gold_grams or 0) for h in ctx.holdings if h.kind == "gold"), Decimal(0))
        if grams > 0:
            lines.append(t(lang, "pulse.link.gold", grams=str(grams.normalize())))
    return lines


async def get_pulse(session: AsyncSession, ctx: Ctx) -> dict[str, Any]:
    day = (await session.execute(select(m.PulseItem.day).where(m.PulseItem.day <= today_ist()).order_by(m.PulseItem.day.desc()).limit(1))).scalar()
    if day is None:
        return {"day": None, "items": [], "say": t(ctx.lang, "pulse.say_none")}
    rows = list((await session.execute(select(m.PulseItem).where(m.PulseItem.day == day).order_by(m.PulseItem.rank))).scalars())
    items = []
    for r in rows:
        title = r.title.get(ctx.lang) or r.title.get("en") or ""
        text = r.summary.get(ctx.lang) or r.summary.get("en") or ""
        lines = personal_lines(ctx, list(r.tags or []))
        items.append({"id": r.id, "topic": r.topic, "title": title, "summary": text, "source_name": r.source_name,
                      "source_url": r.source_url, "tags": r.tags, "for_you": lines})
    spoken = [part for i in items[:2] for part in (f"{i['title']}.", *i["for_you"]) if part]
    say = " ".join(spoken) if items else t(ctx.lang, "pulse.say_none")
    return {"day": day.isoformat(), "is_today": day == today_ist(), "items": items, "say": say}
