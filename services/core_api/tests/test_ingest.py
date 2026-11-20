"""SMS in, transaction out: the demo wordings, merchant matching, the ingest step and the loader's invariants."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from core_api import models as m
from core_api.config import IST
from core_api.demo import sms_wording
from core_api.demo.inject import inject
from core_api.ingest.pipeline import ingest_sms, match_merchant
from core_api.ingest.sms import parse_sms
from core_api.insights.engine import load_merchants
from core_api.ledger import summary
from core_api.ledger.context import clear_caches, load_ctx
from core_api.seed import loader
from core_api.seed.offline import Dataset
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BANKS = ("hdfc", "sbi", "icici", "axis", "kotak", "bob", "other")
WHEN = datetime(2026, 11, 19, 13, 5, 9, tzinfo=IST)


# ---------- every wording the demo writes must read back exactly ----------
@given(st.sampled_from(BANKS), st.integers(min_value=100, max_value=5_00_000_00))
def test_a_written_upi_debit_reads_back(bank: str, paise: int) -> None:
    sender, body = sms_wording.upi_debit(bank, paise=paise, last4="9168", when=WHEN, ref="632313123456", name="Swiggy",
                                         vpa="swiggyorders@axisbank", balance_paise=12_345_67)
    got = parse_sms(sender, body, WHEN, {"9168"})
    assert (got.kind, got.amount_paise, got.account_last4, got.ref_no) == ("debit", paise, "9168", "632313123456")
    assert got.txn_date == WHEN.date()
    assert got.vpa == "swiggyorders@axisbank" or got.counterparty == "SWIGGY"  # each bank prints one or the other


@given(st.sampled_from(BANKS), st.integers(min_value=100, max_value=5_00_000_00))
def test_a_written_imps_credit_reads_back(bank: str, paise: int) -> None:
    sender, body = sms_wording.imps_credit(bank, paise=paise, last4="9168", when=WHEN, ref="632313654321", name="Bonus Payout",
                                           balance_paise=9_87_654_32)
    got = parse_sms(sender, body, WHEN, {"9168"})
    assert (got.kind, got.amount_paise, got.account_last4, got.ref_no) == ("credit", paise, "9168", "632313654321")
    assert got.counterparty == "BONUS PAYOUT" and got.txn_date == WHEN.date()


# ---------- merchant matching ----------
def shop(key: str, name: str, category: str, vpa: str | None = None, aliases: str = "") -> m.Merchant:
    return m.Merchant(key=key, name=name, narration_name=name.upper(), category_id=category, vpa_pattern=vpa, aliases=aliases)


MERCHANTS = {x.key: x for x in (
    shop("swiggy", "Swiggy", "food_delivery", "swiggyorders@axisbank", "SWIGGY LIMITED|BUNDL TECHNOLOGIES"),
    shop("lic", "LIC", "insurance", None, "LIFE INSURANCE CORPORATION OF INDIA"),
    shop("zepto", "Zepto", "groceries", "zepto@icici", "ZEPTO KIRANAKART"),
)}


def test_merchant_by_vpa_name_alias_and_a_name_the_bank_cut_short() -> None:
    assert match_merchant(MERCHANTS, None, "SwiggyOrders@axisbank") is MERCHANTS["swiggy"]
    assert match_merchant(MERCHANTS, "swiggy", None) is MERCHANTS["swiggy"]
    assert match_merchant(MERCHANTS, "BUNDL  TECHNOLOGIES", None) is MERCHANTS["swiggy"]
    assert match_merchant(MERCHANTS, "LIFE INSURANCE CORPORATIO", None) is MERCHANTS["lic"]  # cut at 25 letters
    assert match_merchant(MERCHANTS, "RAGHU TEA STALL", "gpay-1@okbizaxis") is None
    assert match_merchant(MERCHANTS, None, None) is None


# ---------- the ingest step, on a real (in-memory) database ----------
@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    clear_caches()
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        await loader.seed_reference(s)
        yield s
    clear_caches()
    await engine.dispose()


async def linked(session: AsyncSession, persona: str) -> m.User:
    user = m.User(firebase_uid=f"test:{persona}", language="en")
    session.add(user)
    await session.flush()
    await loader.link_persona(session, user, persona)
    await session.commit()
    return user


async def test_a_demo_sms_becomes_one_transaction_and_only_once(session: AsyncSession) -> None:
    user = await linked(session, "first_job")
    ctx = await load_ctx(session, user)
    before = summary.build_summary(ctx)["safe_to_spend"]["spent_today"]["paise"]
    primary = next(a for a in ctx.accounts if a.role == "primary")
    balance = primary.balance_paise

    result = await inject(session, ctx, "swiggy_now")
    await session.commit()
    txn = result.transaction
    assert result.status == "created" and txn is not None
    assert (txn.direction, txn.merchant, txn.category, txn.source, txn.spend_class) == ("debit", "swiggy", "food_delivery", "sms", "flexible")
    assert txn.account_id == primary.id and txn.ref_no == result.parsed.ref_no
    assert primary.balance_paise == balance - txn.amount_paise
    assert result.sms.parse_status == "parsed" and result.sms.transaction_id == txn.id

    ctx = await load_ctx(session, user)
    assert summary.build_summary(ctx)["safe_to_spend"]["spent_today"]["paise"] == before + txn.amount_paise

    # the same message again (a resend, or the account feed catching up) adds nothing
    again = await ingest_sms(session, ctx, await load_merchants(session), result.sms.sender_id, result.sms.body, result.sms.received_at)
    assert again.status == "duplicate" and again.transaction is not None and again.transaction.id == txn.id
    assert primary.balance_paise == balance - txn.amount_paise


async def test_messages_that_must_not_create_a_transaction(session: AsyncSession) -> None:
    user = await linked(session, "first_job")
    ctx = await load_ctx(session, user)
    merchants = await load_merchants(session)
    count = len(ctx.txns)
    now = datetime(2026, 11, 19, 8, 0, tzinfo=UTC)
    otp = await ingest_sms(session, ctx, merchants, "AX-HDFCBK-T", "104850 is OTP for txn of INR 849.00 at FLIPKART on card ending 3757.", now)
    someone_else = await ingest_sms(session, ctx, merchants, "AX-HDFCBK-T",
                                    "Rs.500.00 debited from A/c XX0000 on 19-11-26 to RAVI KUMAR (UPI Ref No 632313000001).", now)
    await session.commit()
    assert (otp.status, otp.sms.parse_status, otp.transaction) == ("ignored", "ignored", None)
    assert (someone_else.status, someone_else.transaction) == ("no_account", None)
    assert len((await load_ctx(session, user)).txns) == count


async def test_salary_preset_is_income_not_spending(session: AsyncSession) -> None:
    user = await linked(session, "shop")
    result = await inject(session, await load_ctx(session, user), "salary_now")
    assert result.transaction is not None
    assert (result.transaction.direction, result.transaction.spend_class, result.transaction.amount_paise) == ("credit", "income", 25_000_00)


# ---------- loader invariants (BUILD_PLAN M2) ----------
def test_transfer_pairs_are_symmetric_and_failed_payments_are_excluded() -> None:
    pairs = failed = 0
    for _, ctx in Dataset("demo").contexts():
        for t in ctx.txns:
            if t.status != "success":
                failed += 1
                assert t.spend_class == "excluded", t.id
            if t.transfer_pair_id:
                other = ctx.by_id[t.transfer_pair_id]
                pairs += 1
                assert other.transfer_pair_id == t.id
                assert other.direction != t.direction and other.amount_paise == t.amount_paise
                assert other.account_id != t.account_id
                assert t.spend_class in ("transfer", "excluded") and other.spend_class in ("transfer", "excluded")
    assert pairs > 0 and failed > 0
