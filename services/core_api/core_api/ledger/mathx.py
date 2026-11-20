"""Pure money maths. Integer paise in, integer paise out. No I/O, no floats."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pocket_common.money import div_half_up

TEN_RUPEES = 1000  # paise


# ---------- calendar ----------
def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def month_start(key: str) -> date:
    y, m = key.split("-")
    return date(int(y), int(m), 1)


def days_in_month(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1]


def month_end(d: date) -> date:
    return date(d.year, d.month, days_in_month(d))


def add_months(d: date, n: int) -> date:
    """Same day n months later, clamped to the month's last day."""
    idx = d.year * 12 + (d.month - 1) + n
    y, m = divmod(idx, 12)
    return date(y, m + 1, min(d.day, calendar.monthrange(y, m + 1)[1]))


def shift_month_key(key: str, n: int) -> str:
    return month_key(add_months(month_start(key), n))


def days_left_incl_today(today: date) -> int:
    return days_in_month(today) - today.day + 1


def budget_month_for(local_date: date, is_salary: bool) -> str:
    """Calendar month in IST, except a salary in the last 3 days of a month counts for the next month."""
    if is_salary and local_date.day > days_in_month(local_date) - 3:
        return month_key(add_months(date(local_date.year, local_date.month, 1), 1))
    return month_key(local_date)


def months_between(start: date, end: date) -> int:
    """Whole calendar months from `start`'s month to `end`'s month, inclusive of both. At least 1."""
    return max(1, (end.year - start.year) * 12 + (end.month - start.month) + 1)


# ---------- safe to spend ----------
@dataclass(frozen=True)
class SafeToSpend:
    income_paise: int
    committed_paise: int
    goal_reserve_paise: int
    spendable_paise: int
    flexible_before_today_paise: int
    flexible_today_paise: int
    days_left: int
    daily_paise: int
    left_today_paise: int


def safe_to_spend(
    income_paise: int,
    committed_paise: int,
    goal_reserve_paise: int,
    flexible_before_today_paise: int,
    flexible_today_paise: int,
    days_left: int,
) -> SafeToSpend:
    """ARCHITECTURE.md §6. `daily` is floored to ₹10 and never shown below zero."""
    if days_left < 1:
        raise ValueError("days_left must be at least 1")
    spendable = income_paise - committed_paise - goal_reserve_paise
    remaining = spendable - flexible_before_today_paise
    per_day = remaining // days_left if remaining > 0 else 0
    daily = (per_day // TEN_RUPEES) * TEN_RUPEES
    return SafeToSpend(
        income_paise=income_paise,
        committed_paise=committed_paise,
        goal_reserve_paise=goal_reserve_paise,
        spendable_paise=spendable,
        flexible_before_today_paise=flexible_before_today_paise,
        flexible_today_paise=flexible_today_paise,
        days_left=days_left,
        daily_paise=daily,
        left_today_paise=daily - flexible_today_paise,
    )


# ---------- loans ----------
def emi_paise(principal_paise: int, annual_rate_bps: int, months: int) -> int:
    """Standard reducing-balance EMI, rounded half-up to the rupee. 0% loans split evenly."""
    if months < 1:
        raise ValueError("months must be at least 1")
    if principal_paise <= 0:
        return 0
    if annual_rate_bps == 0:
        return div_half_up(div_half_up(principal_paise, months), 100) * 100
    r = Decimal(annual_rate_bps) / Decimal(10000) / Decimal(12)
    growth = (Decimal(1) + r) ** months
    emi = Decimal(principal_paise) * r * growth / (growth - Decimal(1))
    rupees = (emi / Decimal(100)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return int(rupees) * 100


def emi_change_for_rate_move(outstanding_paise: int, annual_rate_bps: int, months_left: int, move_bps: int) -> int:
    """How the EMI changes if a floating rate moves by `move_bps` and the tenure stays the same."""
    if months_left < 1 or outstanding_paise <= 0:
        return 0
    new_rate = max(0, annual_rate_bps + move_bps)
    return emi_paise(outstanding_paise, new_rate, months_left) - emi_paise(outstanding_paise, annual_rate_bps, months_left)


def monthly_interest_paise(balance_paise: int, annual_rate_bps: int) -> int:
    """One month of simple interest on a balance (card revolving cost), half-up."""
    return div_half_up(balance_paise * annual_rate_bps, 10000 * 12)


# ---------- splits ----------
class SplitError(ValueError):
    pass


def split_equal(amount_paise: int, member_ids: list[str]) -> dict[str, int]:
    """Floor share each; leftover paise go to members in the given (join) order."""
    if amount_paise < 0:
        raise SplitError("amount must not be negative")
    if not member_ids or len(set(member_ids)) != len(member_ids):
        raise SplitError("members must be unique and non-empty")
    base, rem = divmod(amount_paise, len(member_ids))
    return {m: base + (1 if i < rem else 0) for i, m in enumerate(member_ids)}


def split_percent(amount_paise: int, bps: dict[str, int]) -> dict[str, int]:
    """Basis points summing to 10000; largest-remainder rounding (ties: input order)."""
    if amount_paise < 0:
        raise SplitError("amount must not be negative")
    if not bps or any(v < 0 for v in bps.values()):
        raise SplitError("percentages must be non-negative")
    if sum(bps.values()) != 10000:
        raise SplitError("percentages must sum to 100%")
    shares = {m: amount_paise * v // 10000 for m, v in bps.items()}
    left = amount_paise - sum(shares.values())
    order = sorted(bps, key=lambda m: -(amount_paise * bps[m] % 10000))
    for m in order[:left]:
        shares[m] += 1
    return shares


def split_exact(amount_paise: int, paise: dict[str, int]) -> dict[str, int]:
    if not paise or any(v < 0 for v in paise.values()):
        raise SplitError("shares must be non-negative")
    if sum(paise.values()) != amount_paise:
        raise SplitError("shares must add up to the amount")
    return dict(paise)


@dataclass(frozen=True)
class Payment:
    from_id: str
    to_id: str
    amount_paise: int


def settle_plan(balances: dict[str, int]) -> list[Payment]:
    """Greedy: the largest debtor pays the largest creditor. At most n-1 payments.

    `balances` maps member -> net paise (positive = is owed money). Must sum to zero.
    """
    if sum(balances.values()) != 0:
        raise SplitError("balances must sum to zero")
    debtors = sorted(((m, -b) for m, b in balances.items() if b < 0), key=lambda x: (-x[1], x[0]))
    creditors = sorted(((m, b) for m, b in balances.items() if b > 0), key=lambda x: (-x[1], x[0]))
    plan: list[Payment] = []
    while debtors and creditors:
        d_id, d_amt = debtors[0]
        c_id, c_amt = creditors[0]
        pay = min(d_amt, c_amt)
        plan.append(Payment(d_id, c_id, pay))
        debtors[0] = (d_id, d_amt - pay)
        creditors[0] = (c_id, c_amt - pay)
        if debtors[0][1] == 0:
            debtors.pop(0)
        if creditors[0][1] == 0:
            creditors.pop(0)
        debtors.sort(key=lambda x: (-x[1], x[0]))
        creditors.sort(key=lambda x: (-x[1], x[0]))
    return plan


def median_int(values: list[int]) -> int:
    """Median of integers; the average of the middle two is rounded half-up."""
    if not values:
        raise ValueError("no values")
    s = sorted(values)
    n = len(s)
    if n % 2:
        return s[n // 2]
    return div_half_up(s[n // 2 - 1] + s[n // 2], 2)
