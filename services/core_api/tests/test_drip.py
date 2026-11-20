"""The synthetic drip, the extra SMS wordings it writes, and what survives picking a profile."""

from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta

import pytest
from core_api import models as m
from core_api.config import IST
from core_api.demo import drip, sms_wording
from core_api.ingest.sms import parse_sms
from core_api.insights import engine
from core_api.insights.engine import load_merchants
from core_api.ledger import summary
from core_api.ledger.context import Ctx, clear_caches, load_ctx
from core_api.seed import loader
from core_api.seed.loader import TOLD_BY_USER
from core_api.seed.offline import Dataset
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BANKS = ("hdfc", "sbi", "icici", "axis", "kotak", "bob", "canara", "other")
WHEN = datetime(2026, 11, 20, 13, 5, 9, tzinfo=IST)
DATA_END = date(2026, 11, 19)


# ---------- every extra wording reads back ----------
@given(st.sampled_from(BANKS), st.integers(min_value=100, max_value=5_00_000_00))
def test_a_written_card_spend_reads_back(bank: str, paise: int) -> None:
    sender, body = sms_wording.card_spend(bank, paise=paise, last4="4602", when=WHEN, name="Uber India Systems", limit_paise=1_11_421_00)
    got = parse_sms(sender, body, WHEN, {"4602"})
    assert (got.kind, got.amount_paise, got.account_last4, got.counterparty) == ("debit", paise, "4602", "UBER INDIA SYSTEMS")
    assert got.is_card and got.balance_paise is None and got.txn_date == WHEN.date()


@given(st.sampled_from(BANKS), st.integers(min_value=100, max_value=5_00_000_00))
def test_a_written_card_payment_reads_back(bank: str, paise: int) -> None:
    sender, body = sms_wording.card_payment(bank, paise=paise, last4="4602", when=WHEN)
    got = parse_sms(sender, body, WHEN, {"4602"})
    assert (got.kind, got.amount_paise, got.account_last4, got.counterparty, got.is_card) == ("credit", paise, "4602", None, True)


@given(st.sampled_from(BANKS), st.sampled_from(["NACH", "NEFT", "IMPS"]), st.integers(min_value=100, max_value=5_00_000_00))
def test_a_written_mandate_or_transfer_debit_reads_back(bank: str, channel: str, paise: int) -> None:
    sender, body = sms_wording.account_debit(bank, paise=paise, last4="9168", when=WHEN, name="Indian Clearing Corp Ltd", channel=channel,
                                             balance_paise=12_345_67)
    got = parse_sms(sender, body, WHEN, {"9168"})
    assert (got.kind, got.amount_paise, got.account_last4, got.counterparty) == ("debit", paise, "9168", "INDIAN CLEARING CORP LTD")
    assert got.balance_paise == 12_345_67 and got.txn_date == WHEN.date()


@given(st.sampled_from(BANKS), st.integers(min_value=100, max_value=5_00_000_00))
def test_a_written_upi_debit_to_a_name_reads_back(bank: str, paise: int) -> None:
    sender, body = sms_wording.upi_debit_to_name(bank, paise=paise, last4="9168", when=WHEN, ref="632413123456", name="Lakshmamma",
                                                 balance_paise=12_345_67)
    got = parse_sms(sender, body, WHEN, {"9168"})
    assert (got.kind, got.amount_paise, got.account_last4, got.counterparty, got.ref_no) == ("debit", paise, "9168", "LAKSHMAMMA", "632413123456")


# ---------- which earlier days a day repeats ----------
def test_monthly_items_are_never_skipped_or_paid_twice() -> None:
    assert drip.dated_source_days(date(2026, 11, 20)) == [date(2026, 10, 20)]
    assert drip.dated_source_days(date(2026, 12, 31)) == []  # November has no 31st, and its 30th was due on 30 Dec
    assert drip.dated_source_days(date(2027, 2, 28)) == [date(2027, 1, 28), date(2027, 1, 29), date(2027, 1, 30), date(2027, 1, 31)]
    assert drip.dated_source_days(date(2026, 11, 30)) == [date(2026, 10, 30), date(2026, 10, 31)]
    # across a whole year every source day is used exactly once
    used = [d for n in range(365) for d in drip.dated_source_days(date(2027, 1, 1) + timedelta(days=n))]
    assert len(used) == len(set(used)) == 365


@pytest.fixture(scope="module")
def people() -> dict[str, Ctx]:
    return {str(row["persona_id"]): ctx for row, ctx in Dataset("demo").contexts()}


def test_a_day_repeats_everyday_spending_and_dated_items(people: dict[str, Ctx]) -> None:
    ctx = people["first_job"]
    day = date(2026, 11, 20)
    picked = drip.sources(ctx, day)
    assert picked, "an ordinary day has something to repeat"
    for x in picked:
        assert x.status == "success" and not x.transfer_pair_id and not x.group_expense_id
        assert x.local_date in (day - timedelta(days=28), date(2026, 10, 20))
        if x.local_date == day - timedelta(days=28) and x.recurring_item_id is None and x.spend_class != "income":
            assert x.direction == "debit" and x.spend_class == "flexible"
    times = [x.occurred_at.astimezone(IST).time() for x in picked]
    assert times == sorted(times)


def test_a_planted_double_charge_is_repeated_once(people: dict[str, Ctx]) -> None:
    for ctx in people.values():
        for found in engine.duplicate_charge(ctx):
            second = ctx.by_id[found.data["second_txn_id"]]
            day = second.local_date + timedelta(days=28)
            repeats = [x for x in drip.sources(ctx, day) if x.id in (found.data["first_txn_id"], found.data["second_txn_id"])]
            assert len(repeats) <= 1


# ---------- on a real (in-memory) database ----------
@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    db = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with db.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    clear_caches()
    async with async_sessionmaker(db, expire_on_commit=False)() as s:
        await loader.seed_reference(s)
        yield s
    clear_caches()
    await db.dispose()


async def linked(session: AsyncSession, persona: str) -> m.User:
    user = m.User(firebase_uid=f"test:{persona}", language="en")
    session.add(user)
    await session.flush()
    await loader.link_persona(session, user, persona)
    await session.commit()
    return user


async def test_catch_up_fills_the_missing_days_once(session: AsyncSession) -> None:
    user = await linked(session, "first_job")
    ctx = await load_ctx(session, user)
    ctx.today = DATA_END + timedelta(days=4)  # four days after the data ends: three whole days are missing
    merchants = await load_merchants(session)
    before = len(ctx.txns)
    balance = {a.id: a.balance_paise for a in ctx.accounts}

    created = await drip.catch_up(session, ctx, merchants, DATA_END)
    await session.commit()
    assert created > 0
    rows = list((await session.execute(select(m.Transaction).where(m.Transaction.user_id == user.id, m.Transaction.source == "sms"))).scalars())
    assert len(rows) == created
    assert {r.local_date for r in rows} <= {DATA_END + timedelta(days=n) for n in (1, 2, 3)}
    assert len({r.local_date for r in rows}) == 3  # each missing day got its transactions; today is left alone

    # every repeat was classified like the payment it repeats, through the parser
    by_id = {t.id: t for t in ctx.txns}
    messages = list((await session.execute(select(m.SmsMessage).where(m.SmsMessage.user_id == user.id))).scalars())
    assert len(messages) >= created and all(s.parse_status in ("parsed", "duplicate") for s in messages)
    checked = 0
    for s in messages:
        if s.parse_status != "parsed" or not s.ground_truth:
            continue
        new, old = by_id[s.transaction_id], by_id[s.ground_truth["repeats"]]
        assert (new.amount_paise, new.direction, new.account_id) == (old.amount_paise, old.direction, old.account_id)
        assert (new.category, new.spend_class, new.recurring_item_id) == (old.category, old.spend_class, old.recurring_item_id), s.body
        checked += 1
    assert checked == created

    # the balances moved by exactly what arrived
    for a in ctx.accounts:
        moved = sum((r.amount_paise if r.direction == "credit" else -r.amount_paise) for r in rows if r.account_id == a.id)
        expected = balance[a.id] + (-moved if a.type == "credit_card" else moved)
        assert a.balance_paise == expected, a.institution

    # running it again adds nothing
    again = await drip.catch_up(session, ctx, merchants, DATA_END)
    assert again == 0
    assert len((await load_ctx(session, user)).txns) == before + created


async def test_nothing_is_added_on_the_day_after_the_data_ends(session: AsyncSession) -> None:
    user = await linked(session, "student")
    ctx = await load_ctx(session, user)
    ctx.today = DATA_END + timedelta(days=1)  # yesterday is the data's last day: already covered
    assert await drip.catch_up(session, ctx, await load_merchants(session), DATA_END) == 0


async def test_the_drip_plants_no_new_insights_of_the_six_types(session: AsyncSession) -> None:
    user = await linked(session, "family")
    ctx = await load_ctx(session, user)
    wanted = {(f.type, f.fingerprint) for f in engine.detect_all(ctx) if f.type in engine.PLANTED_TYPES}
    ctx.today = DATA_END + timedelta(days=8)
    await drip.catch_up(session, ctx, await load_merchants(session), DATA_END)
    await session.commit()
    fresh = await load_ctx(session, user)
    fresh.today = ctx.today
    after = {(f.type, f.fingerprint) for f in engine.detect_all(fresh) if f.type in engine.PLANTED_TYPES}
    new = {kind for kind, _ in after - wanted}
    assert "duplicate_charge" not in new and "forgotten_subscription" not in new and "price_hike" not in new
    assert summary.build_summary(fresh)["safe_to_spend"]["daily"]["paise"] >= 0


# ---------- what the user told the mascot survives picking a profile ----------
async def test_what_the_user_told_the_mascot_survives_linking_and_switching(session: AsyncSession) -> None:
    user = m.User(firebase_uid="test:told", language="en")
    session.add(user)
    await session.flush()
    session.add(m.ProfileFact(user_id=user.id, key="saving_for", value="a trip to Ladakh with my sister", source=TOLD_BY_USER, language="en"))
    await session.commit()

    for persona in ("first_job", "investor"):  # link, then switch
        await loader.link_persona(session, user, persona)
        await session.commit()
        facts = {f.key: f for f in (await session.execute(select(m.ProfileFact).where(m.ProfileFact.user_id == user.id))).scalars()}
        assert facts["saving_for"].value == "a trip to Ladakh with my sister" and facts["saving_for"].source == TOLD_BY_USER
        assert facts["worries"].source == "onboarding"  # the rest still comes from the profile they picked
        assert len([f for f in facts.values() if f.key == "saving_for"]) == 1
