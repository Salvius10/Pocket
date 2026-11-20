"""Demo presets: add one believable transaction 'now' so the demo can show a live change."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from core_api import models as m
from core_api.config import IST
from core_api.ledger import mathx, summary
from core_api.ledger.classify import spend_class
from core_api.ledger.context import Ctx, bump

RS = 100


async def inject(session: AsyncSession, ctx: Ctx, preset: str) -> m.Transaction:
    primary = next((a for a in ctx.accounts if a.role == "primary"), None) or next(a for a in ctx.accounts if a.type in ("savings", "current"))
    now = datetime.now(IST)
    if now.date() != ctx.today:  # POCKET_TODAY is frozen: keep the injected row on the demo day
        now = datetime(ctx.today.year, ctx.today.month, ctx.today.day, 13, 5, tzinfo=IST)
    if preset == "salary_now":
        amount, direction, category, merchant, name, vpa = 25_000 * RS, "credit", "other_income", None, "Bonus", None
    elif preset == "chai_now":
        amount, direction, category, merchant, name, vpa = 40 * RS, "debit", "eating_out", None, "Tea Stall", "gpay-11223344556@okbizaxis"
    else:
        # A Swiggy order sized to push the food delivery pocket just past its limit (capped at a normal order).
        pocket = next((p for p in summary.pockets(ctx) if "food_delivery" in p["category_ids"]), None)
        left = pocket["left"]["paise"] if pocket else 0
        amount = min(1_200 * RS, max(349 * RS, left + 120 * RS))
        direction, category, merchant, name, vpa = "debit", "food_delivery", "swiggy", "Swiggy", "swiggyorders@axisbank"
    cat = ctx.categories[category]
    signed = amount if direction == "credit" else -amount
    primary.balance_paise += signed
    ref = f"{now:%y}"[-1] + f"{now.timetuple().tm_yday:03d}{now.hour:02d}" + f"{uuid4().int % 1_000_000:06d}"
    txn = m.Transaction(
        user_id=ctx.user.id, account_id=primary.id, occurred_at=now.astimezone(UTC), local_date=now.date(),
        budget_month=mathx.month_key(now.date()), amount_paise=amount, personal_amount_paise=amount, direction=direction, mode="upi",
        status="success", kind="upi_p2m" if direction == "debit" else "upi_in", merchant=merchant, merchant_name=name,
        counterparty_name=name.upper(), counterparty_vpa=vpa, category=category,
        spend_class=spend_class(status="success", hidden=False, is_reversal=False, category_kind=cat.kind,
                                category_default_class=cat.default_class, recurring_kind=None),
        narration=f"UPI/{name.upper()}/{ref}/UPI", ref_no=ref, balance_after_paise=primary.balance_paise, source="sms",
    )
    session.add(txn)
    await bump(session, ctx.user)
    return txn
