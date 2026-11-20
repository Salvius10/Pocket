from datetime import UTC, date, datetime, timedelta

import pytest
from core_api.config import IST
from core_api.ledger import mathx
from core_api.ledger.classify import next_due_date, spend_class
from core_api.nudges.planner import Candidate, delivery_time, in_quiet_hours, pick
from hypothesis import given
from hypothesis import strategies as st

RS = 100


# ---------- worked examples from BUILD_PLAN M3 ----------
def test_safe_to_spend_worked_example() -> None:
    # ₹62,000 income, ₹20,697 committed, ₹10,000 goal reserve, ₹24,100 spent before today, 11 days left
    s = mathx.safe_to_spend(62_000 * RS, 20_697 * RS, 10_000 * RS, 24_100 * RS, 280 * RS, 11)
    assert s.daily_paise == 650 * RS
    assert s.left_today_paise == 370 * RS


def test_safe_to_spend_never_negative_daily() -> None:
    s = mathx.safe_to_spend(10_000 * RS, 9_000 * RS, 2_000 * RS, 500 * RS, 100 * RS, 5)
    assert s.daily_paise == 0
    assert s.left_today_paise == -100 * RS


def test_emi_worked_example() -> None:
    assert mathx.emi_paise(10_00_000 * RS, 1200, 12) == 88_849 * RS


def test_zero_cost_emi_splits_evenly() -> None:
    assert mathx.emi_paise(13_491 * RS, 0, 9) == 1_499 * RS


def test_equal_split_worked_example() -> None:
    assert mathx.split_equal(1_000 * RS, ["a", "b", "c"]) == {"a": 33_334, "b": 33_333, "c": 33_333}


def test_percent_split_largest_remainder() -> None:
    shares = mathx.split_percent(1_000 * RS + 1, {"a": 3334, "b": 3333, "c": 3333})
    assert sum(shares.values()) == 1_000 * RS + 1


def test_exact_split_must_sum() -> None:
    with pytest.raises(mathx.SplitError):
        mathx.split_exact(1_000, {"a": 400, "b": 500})


def test_budget_month_salary_rule() -> None:
    assert mathx.budget_month_for(date(2026, 10, 30), is_salary=True) == "2026-11"  # last 3 days -> next month
    assert mathx.budget_month_for(date(2026, 10, 28), is_salary=True) == "2026-10"
    assert mathx.budget_month_for(date(2026, 10, 30), is_salary=False) == "2026-10"
    assert mathx.budget_month_for(date(2026, 12, 31), is_salary=True) == "2027-01"


def test_spend_class_precedence() -> None:
    base = dict(hidden=False, is_reversal=False, category_default_class="flexible", recurring_kind=None)
    assert spend_class(status="reversed", category_kind="expense", **base) == "excluded"
    assert spend_class(status="success", category_kind="refund", **base) == "refund"
    assert spend_class(status="success", category_kind="transfer", **base) == "transfer"
    assert spend_class(status="success", category_kind="income", **base) == "income"
    assert spend_class(status="success", category_kind="saving", **base) == "saving"
    assert spend_class(status="success", category_kind="expense", **{**base, "recurring_kind": "subscription"}) == "committed"
    assert spend_class(status="success", category_kind="expense", **{**base, "category_default_class": "committed"}) == "committed"
    assert spend_class(status="success", category_kind="expense", **base) == "flexible"


def test_next_due_monthly_after_payment() -> None:
    nd = next_due_date(cadence="monthly", day=5, start_date=None, end_date=None, last_paid=date(2026, 11, 5), typical_gap_days=30, today=date(2026, 11, 20))
    assert nd == date(2026, 12, 5)


def test_next_due_stops_after_end_date() -> None:
    nd = next_due_date(cadence="monthly", day=2, start_date=None, end_date=date(2026, 11, 2), last_paid=date(2026, 11, 2), typical_gap_days=30, today=date(2026, 11, 20))
    assert nd is None


# ---------- properties ----------
ids = st.lists(st.text(alphabet="abcdefgh", min_size=1, max_size=3), min_size=1, max_size=8, unique=True)


@given(st.integers(min_value=0, max_value=10**10), ids)
def test_equal_shares_always_sum_to_the_amount(amount: int, members: list[str]) -> None:
    shares = mathx.split_equal(amount, members)
    assert sum(shares.values()) == amount
    assert max(shares.values()) - min(shares.values()) <= 1
    assert list(shares.values()) == sorted(shares.values(), reverse=True)  # leftovers go in join order


@given(st.integers(min_value=0, max_value=10**10), st.lists(st.integers(min_value=0, max_value=10000), min_size=1, max_size=7))
def test_percent_shares_always_sum_to_the_amount(amount: int, weights: list[int]) -> None:
    total = sum(weights)
    if total == 0:
        return
    bps = [w * 10000 // total for w in weights]
    bps[0] += 10000 - sum(bps)
    shares = mathx.split_percent(amount, {f"m{i}": b for i, b in enumerate(bps)})
    assert sum(shares.values()) == amount
    assert all(v >= 0 for v in shares.values())


@given(st.lists(st.integers(min_value=-(10**8), max_value=10**8), min_size=1, max_size=9))
def test_settle_plan_zeroes_every_balance_in_at_most_n_minus_1(raw: list[int]) -> None:
    balances = {f"m{i}": v for i, v in enumerate(raw)}
    balances["last"] = -sum(raw)
    plan = mathx.settle_plan(balances)
    assert len(plan) <= max(0, len(balances) - 1)
    after = dict(balances)
    for p in plan:
        assert p.amount_paise > 0
        after[p.from_id] += p.amount_paise
        after[p.to_id] -= p.amount_paise
    assert all(v == 0 for v in after.values())


@given(st.integers(min_value=1, max_value=10**11), st.integers(min_value=1, max_value=3600), st.integers(min_value=1, max_value=360))
def test_emi_repays_the_loan(principal: int, bps: int, months: int) -> None:
    emi = mathx.emi_paise(principal, bps, months)
    assert emi * months >= principal - 100 * months  # never less than the principal (to the rupee rounding)


@given(st.integers(0, 10**9), st.integers(0, 10**9), st.integers(0, 10**9), st.integers(0, 10**9), st.integers(0, 10**7), st.integers(1, 31))
def test_safe_to_spend_invariants(income: int, committed: int, reserve: int, before: int, today: int, days: int) -> None:
    s = mathx.safe_to_spend(income, committed, reserve, before, today, days)
    assert s.daily_paise >= 0
    assert s.daily_paise % 1000 == 0  # floored to ₹10
    assert s.daily_paise * days <= max(0, income - committed - reserve - before)
    assert s.left_today_paise == s.daily_paise - today


# ---------- nudges ----------
def ist(h: int, m: int = 0, day: int = 20) -> datetime:
    return datetime(2026, 11, day, h, m, tzinfo=IST)


def test_third_nudge_on_the_same_day_is_suppressed() -> None:
    candidates = [Candidate("bill_due", "b1"), Candidate("overspend", "o1"), Candidate("goal_reached", "g1")]
    chosen = pick(candidates, set(), {}, 2, ist(14), "22:00", "08:00")
    assert [c.kind for c, _ in chosen] == ["bill_due", "overspend"]
    # two already delivered today: nothing more goes out
    assert pick(candidates, set(), {ist(14).date(): 2}, 2, ist(15), "22:00", "08:00") == []


def test_nudge_at_23_moves_to_8() -> None:
    when = delivery_time(ist(23, 0), "22:00", "08:00")
    assert when == ist(8, 0, day=21)
    chosen = pick([Candidate("bill_due", "b1")], set(), {}, 2, ist(23, 0), "22:00", "08:00")
    assert chosen[0][1] == ist(8, 0, day=21)


def test_postponed_nudge_counts_against_the_delivery_day() -> None:
    tomorrow = ist(8, day=21).date()
    assert pick([Candidate("bill_due", "b1")], set(), {tomorrow: 2}, 2, ist(23), "22:00", "08:00") == []


def test_quiet_hours_window_wraps_midnight() -> None:
    assert in_quiet_hours(ist(22, 0), "22:00", "08:00")
    assert in_quiet_hours(ist(3, 30), "22:00", "08:00")
    assert not in_quiet_hours(ist(8, 0), "22:00", "08:00")
    assert not in_quiet_hours(ist(21, 59), "22:00", "08:00")


def test_priority_order_and_dedupe() -> None:
    candidates = [Candidate("insight", "i1"), Candidate("group_request", "gr"), Candidate("bill_due", "b1")]
    chosen = pick(candidates, {"b1"}, {}, 2, ist(10), "22:00", "08:00")
    assert [c.kind for c, _ in chosen] == ["group_request", "insight"]  # b1 was already sent


def test_daily_max_is_capped_at_two_and_zero_means_none() -> None:
    many = [Candidate("bill_due", f"b{i}") for i in range(5)]
    assert len(pick(many, set(), {}, 9, ist(10), "22:00", "08:00")) == 2
    assert pick(many, set(), {}, 0, ist(10), "22:00", "08:00") == []


_ = (UTC, timedelta)
