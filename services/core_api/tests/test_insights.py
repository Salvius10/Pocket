"""The insight engine: the demo answer key, and the rules that decide what counts."""

from datetime import UTC, date, datetime, timedelta

from core_api import models as m
from core_api.config import IST
from core_api.insights import engine
from core_api.ledger.context import Ctx, make_ctx
from core_api.seed.offline import Dataset

RS = 100
TODAY = date(2026, 11, 19)


# ---------- the shipped answer key ----------
def test_demo_personas_match_the_answer_key() -> None:
    ds = Dataset("demo")
    seen = 0
    for user_row, ctx in ds.contexts():
        found = engine.detect_all(ctx, ds.merchants)
        got = {(f.type, f.fingerprint) for f in found if f.type in engine.PLANTED_TYPES}
        assert got == ds.planted(str(user_row["user_id"])), user_row["persona_id"]
        seen += 1
    assert seen == 6


# ---------- hand-built ledgers ----------
def at(day: date, hour: int = 10, minute: int = 0, second: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=IST).astimezone(UTC)


def debit(n: int, when: datetime, rupees: int, *, merchant: str | None = None, name: str = "", item: str | None = None,
          spend_class: str = "committed") -> m.Transaction:
    local = when.astimezone(IST).date()
    return m.Transaction(
        id=f"txn-{n}", user_id="u", account_id="acct", occurred_at=when, local_date=local,
        budget_month=local.isoformat()[:7], amount_paise=rupees * RS, personal_amount_paise=rupees * RS,
        direction="debit", mode="upi", status="success", kind="upi_p2m", merchant=merchant, merchant_name=name,
        counterparty_name=name.upper() or None, category="other_expense", spend_class=spend_class, narration="",
        recurring_item_id=item, hidden=False, source="aa",
    )


def bill(item_id: str, name: str, kind: str = "bill") -> m.RecurringItem:
    return m.RecurringItem(
        id=item_id, user_id="u", key=item_id, kind=kind, source_kind=kind, name=name, cadence="monthly", day=7,
        amount_paise=0, amount_is_variable=False, status="active",
    )


def ledger(txns: list[m.Transaction], recurring: list[m.RecurringItem] | None = None) -> Ctx:
    user = m.User(id="u", firebase_uid="test:u", language="en")
    return make_ctx(
        user, TODAY, settings=None, categories={}, accounts=[], txns=sorted(txns, key=lambda t: t.occurred_at),
        recurring=recurring or [], loans=[], holdings=[], pockets=[], adjustments=[], goals=[], contributions=[],
        statements=[], nav={},
    )


def monthly(amounts: list[int], *, merchant: str | None = None, name: str = "", item: str | None = None,
            start: int = 0) -> list[m.Transaction]:
    """One charge a month, the last one on 7 Nov 2026."""
    days = [date(2026, 11 - i, 7) for i in range(len(amounts) - 1, -1, -1)]
    return [debit(start + i, at(d), amount, merchant=merchant, name=name, item=item)
            for i, (d, amount) in enumerate(zip(days, amounts, strict=True))]


def test_price_hike_on_a_bill_with_no_merchant() -> None:
    ctx = ledger(monthly([2500, 2500, 2500, 2500, 2900], item="society", name="Green Park Society"),
                 [bill("society", "Society maintenance")])
    (found,) = engine.price_hike(ctx)
    assert found.fingerprint == "price_hike:None:290000"
    assert found.data["name"] == "Society maintenance"
    assert (found.data["old_paise"], found.data["new_paise"], found.data["pct"]) == (2500 * RS, 2900 * RS, 16)
    assert found.data["since"] == "2026-11-07"


def test_rent_and_emi_steps_are_not_price_hikes() -> None:
    for kind in ("rent", "emi", "sip"):
        ctx = ledger(monthly([15000, 15000, 15000, 15000, 17000], item="x", name="Landlord"), [bill("x", "Monthly", kind)])
        assert engine.price_hike(ctx) == []


def test_a_variable_bill_is_not_a_price_hike() -> None:
    ctx = ledger(monthly([1200, 1500, 1100, 1300, 1700], item="power", name="Electricity"), [bill("power", "Electricity")])
    assert engine.price_hike(ctx) == []


def test_a_small_or_old_step_is_not_a_price_hike() -> None:
    small = ledger(monthly([500, 500, 500, 500, 515], merchant="netflix", name="Netflix"))  # under 10%
    assert engine.price_hike(small) == []
    old = [debit(i, at(date(2026, m_, 7)), amount, merchant="netflix", name="Netflix")
           for i, (m_, amount) in enumerate([(4, 500), (5, 500), (6, 500), (7, 500), (8, 600)])]  # last charge in August
    assert engine.price_hike(ledger(old)) == []


def test_two_plans_from_one_company_are_separate_series() -> None:
    mobile = monthly([299, 299, 299, 299, 299], merchant="airtel", name="Airtel", item="mobile")
    fibre = monthly([942, 942, 942, 942, 1060], merchant="airtel", name="Airtel", item="fibre", start=100)
    for t in fibre:  # the fibre bill is paid a few hours after the mobile one
        t.occurred_at += timedelta(hours=3)
    ctx = ledger(mobile + fibre, [bill("mobile", "Airtel mobile"), bill("fibre", "Airtel Xstream Fiber")])
    (found,) = engine.price_hike(ctx)
    assert found.fingerprint == "price_hike:airtel:106000"
    assert found.data["old_paise"] == 942 * RS


def test_duplicate_at_a_known_merchant_within_ten_minutes() -> None:
    day = date(2026, 11, 10)
    ctx = ledger([debit(1, at(day, 13, 0), 382, merchant="swiggy", name="Swiggy", spend_class="flexible"),
                  debit(2, at(day, 13, 9), 382, merchant="swiggy", name="Swiggy", spend_class="flexible")])
    (found,) = engine.duplicate_charge(ctx)
    assert found.fingerprint == "dup:txn-2"
    late = ledger([debit(1, at(day, 13, 0), 382, merchant="swiggy", name="Swiggy", spend_class="flexible"),
                   debit(2, at(day, 13, 11), 382, merchant="swiggy", name="Swiggy", spend_class="flexible")])
    assert engine.duplicate_charge(late) == []


def test_a_second_cup_of_tea_is_not_a_duplicate() -> None:
    day = date(2026, 11, 10)
    nine_minutes = ledger([debit(1, at(day, 9, 0), 25, name="Raghu Tea Stall", spend_class="flexible"),
                           debit(2, at(day, 9, 9), 25, name="Raghu Tea Stall", spend_class="flexible")])
    assert engine.duplicate_charge(nine_minutes) == []
    double_tap = ledger([debit(1, at(day, 9, 0, 0), 25, name="Raghu Tea Stall", spend_class="flexible"),
                         debit(2, at(day, 9, 0, 40), 25, name="Raghu Tea Stall", spend_class="flexible")])
    assert [f.fingerprint for f in engine.duplicate_charge(double_tap)] == ["dup:txn-2"]


def test_different_amounts_or_accounts_are_not_duplicates() -> None:
    day = date(2026, 11, 10)
    a = debit(1, at(day, 13, 0), 382, merchant="swiggy", name="Swiggy", spend_class="flexible")
    b = debit(2, at(day, 13, 2), 383, merchant="swiggy", name="Swiggy", spend_class="flexible")
    assert engine.duplicate_charge(ledger([a, b])) == []
    c = debit(3, at(day, 13, 2), 382, merchant="swiggy", name="Swiggy", spend_class="flexible")
    c.account_id = "another-card"
    assert engine.duplicate_charge(ledger([a, c])) == []
