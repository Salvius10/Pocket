"""The synthetic drip: keeps a demo profile's data current after the dataset's last day.

The shipped dataset ends on a fixed day. For every day after it, up to yesterday, the drip adds
an ordinary day for that person, built from their own history:

- everyday spending: what they spent on the same weekday four weeks earlier;
- dated items: bills, EMIs, SIPs, subscriptions, income and card-bill payments from the same
  day of the previous month.

Each one is written as a synthetic bank SMS in the wording of the account's bank and goes through
the SMS parser and the ingest step, exactly like a message arriving (ARCHITECTURE.md §7.5). It
is deterministic: the same person and day always produce the same messages.

Synthetic only. Nothing here reads a real SMS or talks to a bank.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api import models as m
from core_api.config import IST
from core_api.demo import sms_wording
from core_api.ingest.pipeline import ingest_sms
from core_api.ledger import mathx
from core_api.ledger.context import Ctx

MAX_DAYS = 14  # how far back one catch-up goes; older gaps stay empty
FACT_KEY = "demo.drip_through"  # profile fact: the last day the drip has covered
CHANNELS = {"nach": "NACH", "autopay": "NACH", "neft": "NEFT", "imps": "IMPS"}


def dated_source_days(day: date) -> list[date]:
    """The days of the previous month whose monthly items fall due on `day`. Usually one: the same
    day number. On the last day of a short month it also takes the later days the month lacks
    (28 Feb collects 28-31 Jan), so nothing monthly is skipped or paid twice."""
    previous = mathx.add_months(date(day.year, day.month, 1), -1)
    last = mathx.days_in_month(previous)
    days = [date(previous.year, previous.month, day.day)] if day.day <= last else []
    if day.day == mathx.days_in_month(day):
        days += [date(previous.year, previous.month, d) for d in range(day.day + 1, last + 1)]
    return days


def sources(ctx: Ctx, day: date) -> list[m.Transaction]:
    """The earlier transactions this day repeats, in time-of-day order."""
    weekday_source = day - timedelta(days=28)
    dated = set(dated_source_days(day))
    live_items = {r.id for r in ctx.recurring if r.status == "active"}
    picked: list[m.Transaction] = []
    for x in ctx.txns:
        if x.status != "success" or x.hidden or x.group_expense_id or x.reversal_of_id or x.refund_of_id or x.transfer_pair_id:
            continue
        everyday = (x.local_date == weekday_source and x.direction == "debit" and x.spend_class == "flexible"
                    and x.recurring_item_id is None and x.mode in ("upi", "card"))
        monthly = x.local_date in dated and (
            (x.recurring_item_id is not None and x.recurring_item_id in live_items)
            or (x.direction == "credit" and x.spend_class == "income")
            or x.kind in ("card_bill_pay", "card_payment_in")
        )
        if everyday or monthly:
            picked.append(x)
    picked.sort(key=lambda x: (x.occurred_at.astimezone(IST).time(), x.id))
    out: list[m.Transaction] = []
    for x in picked:  # a charge that was doubled by mistake is not repeated as two
        twin = next((y for y in out if y.account_id == x.account_id and y.amount_paise == x.amount_paise and y.direction == x.direction
                     and (y.merchant or y.counterparty_name) == (x.merchant or x.counterparty_name)
                     and abs((x.occurred_at - y.occurred_at).total_seconds()) % 86_400 <= 600), None)
        if twin is None:
            out.append(x)
    return out


def write_sms(ctx: Ctx, x: m.Transaction, account: m.Account, when: datetime) -> tuple[str, str]:
    """The synthetic SMS for repeating `x` at `when`."""
    bank = sms_wording.bank_of(account.institution_code, account.institution)
    last4 = account.masked_number[-4:]
    seed = uuid5(NAMESPACE_URL, f"pocket-drip:{ctx.user.id}:{x.id}:{when.date().isoformat()}").int
    ref = f"{when:%y}"[-1] + f"{when.timetuple().tm_yday:03d}{when.hour:02d}{seed % 1_000_000:06d}"
    name = x.counterparty_name or x.merchant_name or "Payment"
    amount = x.amount_paise
    if account.type == "credit_card":
        if x.direction == "credit":
            return sms_wording.card_payment(bank, paise=amount, last4=last4, when=when)
        limit = max(0, (account.credit_limit_paise or 0) - account.balance_paise - amount)
        return sms_wording.card_spend(bank, paise=amount, last4=last4, when=when, name=name, limit_paise=limit)
    if x.direction == "credit":
        return sms_wording.imps_credit(bank, paise=amount, last4=last4, when=when, ref=ref, name=name, balance_paise=account.balance_paise + amount)
    balance = account.balance_paise - amount
    if x.mode == "upi":
        if x.counterparty_vpa:
            return sms_wording.upi_debit(bank, paise=amount, last4=last4, when=when, ref=ref, name=name, vpa=x.counterparty_vpa, balance_paise=balance)
        return sms_wording.upi_debit_to_name(bank, paise=amount, last4=last4, when=when, ref=ref, name=name, balance_paise=balance)
    return sms_wording.account_debit(bank, paise=amount, last4=last4, when=when, name=name, channel=CHANNELS.get(x.mode, "NEFT"), balance_paise=balance)


async def drip_day(session: AsyncSession, ctx: Ctx, merchants: dict[str, m.Merchant], day: date) -> int:
    """Add `day`'s transactions for this person. Returns how many were created."""
    created = 0
    for x in sources(ctx, day):
        account = ctx.account(x.account_id)
        if account is None:
            continue
        clock = x.occurred_at.astimezone(IST)
        when = datetime(day.year, day.month, day.day, clock.hour, clock.minute, clock.second, tzinfo=IST)
        sender, body = write_sms(ctx, x, account, when)
        result = await ingest_sms(session, ctx, merchants, sender, body, when)
        result.sms.ground_truth = {"drip": day.isoformat(), "repeats": x.id}
        if result.status == "created" and result.transaction is not None:
            created += 1
            ctx.txns.append(result.transaction)  # so a later day in the same catch-up can build on it
    return created


async def catch_up(session: AsyncSession, ctx: Ctx, merchants: dict[str, m.Merchant], data_end: date) -> int:
    """Add every missing day from the day after the data ends (or the last day already covered)
    up to yesterday. Returns how many transactions were created; 0 means nothing changed."""
    yesterday = ctx.today - timedelta(days=1)
    fact = (await session.execute(
        select(m.ProfileFact).where(m.ProfileFact.user_id == ctx.user.id, m.ProfileFact.key == FACT_KEY)
    )).scalar_one_or_none()
    covered = date.fromisoformat(fact.value) if fact is not None else data_end
    if covered >= yesterday:
        return 0
    day = max(covered + timedelta(days=1), ctx.today - timedelta(days=MAX_DAYS))
    created = 0
    while day <= yesterday:
        created += await drip_day(session, ctx, merchants, day)
        day += timedelta(days=1)
    if fact is None:
        session.add(m.ProfileFact(user_id=ctx.user.id, key=FACT_KEY, value=yesterday.isoformat(), source="system"))
    else:
        fact.value = yesterday.isoformat()
    await session.flush()
    return created
