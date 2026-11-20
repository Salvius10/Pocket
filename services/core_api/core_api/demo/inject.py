"""Demo presets: add one believable transaction 'now' so the demo can show a live change.

The transaction arrives the way a real one would: a synthetic bank SMS in the wording of the
user's own bank is written, then read by the SMS parser and stored by the ingest step. Nothing is
inserted directly, so the demo exercises the same path a bank message would take.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from core_api.config import IST
from core_api.demo import sms_wording
from core_api.ingest.pipeline import Ingested, ingest_sms
from core_api.insights.engine import load_merchants
from core_api.ledger import summary
from core_api.ledger.context import Ctx

RS = 100


class InjectError(RuntimeError):
    """The synthetic SMS did not become a transaction (the reason is the parser's status)."""


async def inject(session: AsyncSession, ctx: Ctx, preset: str) -> Ingested:
    primary = next((a for a in ctx.accounts if a.role == "primary"), None) or next(a for a in ctx.accounts if a.type in ("savings", "current"))
    now = datetime.now(IST)
    if now.date() != ctx.today:  # POCKET_TODAY is frozen: keep the injected row on the demo day
        now = datetime(ctx.today.year, ctx.today.month, ctx.today.day, 13, 5, tzinfo=IST)
    bank = sms_wording.bank_of(primary.institution_code, primary.institution)
    last4 = primary.masked_number[-4:]
    ref = f"{now:%y}"[-1] + f"{now.timetuple().tm_yday:03d}{now.hour:02d}" + f"{uuid4().int % 1_000_000:06d}"

    if preset == "salary_now":
        amount = 25_000 * RS
        sender, body = sms_wording.imps_credit(bank, paise=amount, last4=last4, when=now, ref=ref, name="Bonus Payout",
                                               balance_paise=primary.balance_paise + amount)
    elif preset == "chai_now":
        amount = 40 * RS
        sender, body = sms_wording.upi_debit(bank, paise=amount, last4=last4, when=now, ref=ref, name="Tea Stall",
                                             vpa="gpay-11223344556@okbizaxis", balance_paise=primary.balance_paise - amount)
    else:
        # A Swiggy order sized to push the food delivery pocket just past its limit (capped at a normal order).
        pocket = next((p for p in summary.pockets(ctx) if "food_delivery" in p["category_ids"]), None)
        left = pocket["left"]["paise"] if pocket else 0
        amount = min(1_200 * RS, max(349 * RS, left + 120 * RS))
        sender, body = sms_wording.upi_debit(bank, paise=amount, last4=last4, when=now, ref=ref, name="Swiggy",
                                             vpa="swiggyorders@axisbank", balance_paise=primary.balance_paise - amount)

    result = await ingest_sms(session, ctx, await load_merchants(session), sender, body, now)
    if result.status != "created" or result.transaction is None:
        raise InjectError(f"the demo SMS was not turned into a transaction: {result.status}")
    return result
