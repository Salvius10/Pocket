"""Spend class and next-due logic. Decided by code on every transaction (ARCHITECTURE.md §5)."""

from __future__ import annotations

from datetime import date, timedelta

from core_api.ledger.mathx import add_months

# data `recurring_items.kind` -> app kind (data/README.md §3)
RECURRING_KIND_MAP = {
    "subscription": "subscription",
    "bill": "bill", "recharge": "bill", "lpg": "bill", "milk": "bill", "fees": "bill",
    "maid": "bill", "remittance": "bill",
    "rent": "rent", "emi": "emi", "insurance": "insurance",
    "sip": "sip", "ppf": "sip",
    "salary": "salary",
}
COMMITTED_RECURRING_KINDS = {"rent", "emi", "bill", "subscription", "insurance"}
SALARY_CATEGORIES = {"salary"}


def spend_class(
    *,
    status: str,
    hidden: bool,
    is_reversal: bool,
    category_kind: str,
    category_default_class: str,
    recurring_kind: str | None,
) -> str:
    """excluded -> refund -> transfer -> income -> saving -> committed -> flexible."""
    if status != "success" or hidden or is_reversal:
        return "excluded"
    if category_kind == "refund":
        return "refund"
    if category_kind == "transfer":
        return "transfer"
    if category_kind == "income":
        return "income"
    if category_kind == "saving":
        return "saving"
    if category_default_class == "committed" or recurring_kind in COMMITTED_RECURRING_KINDS:
        return "committed"
    return "flexible"


def next_due_date(
    *,
    cadence: str,
    day: int | None,
    start_date: date | None,
    end_date: date | None,
    last_paid: date | None,
    typical_gap_days: int | None,
    today: date,
) -> date | None:
    """When a recurring item is next expected. None once it has ended."""

    def clamp(d: date) -> date | None:
        return None if end_date is not None and d > end_date else d

    if cadence in ("every_28d", "every_n_days"):
        gap = 28 if cadence == "every_28d" else (typical_gap_days or 30)
        base = last_paid or start_date or today
        nxt = base + timedelta(days=gap) if last_paid else base
        while nxt < today - timedelta(days=gap):
            nxt += timedelta(days=gap)
        return clamp(nxt)

    step = {"monthly": 1, "bimonthly": 2, "quarterly": 3, "yearly": 12}.get(cadence, 1)
    d = day or (last_paid.day if last_paid else (start_date.day if start_date else 1))
    if last_paid is not None:
        anchor = date(last_paid.year, last_paid.month, 1)
        nxt = add_months(anchor, step)
        nxt = add_months(date(nxt.year, nxt.month, 28), 0).replace(day=min(d, _last_day(nxt)))
        # paid early for a later cycle (e.g. on the 30th for the 1st): never schedule before the payment
        while nxt <= last_paid:
            nxt = _same_day(add_months(date(nxt.year, nxt.month, 1), step), d)
        return clamp(nxt)
    base = start_date or today
    nxt = _same_day(date(base.year, base.month, 1), d)
    if nxt < base:
        nxt = _same_day(add_months(date(nxt.year, nxt.month, 1), step), d)
    return clamp(nxt)


def _last_day(d: date) -> int:
    import calendar

    return calendar.monthrange(d.year, d.month)[1]


def _same_day(first_of_month: date, day: int) -> date:
    return first_of_month.replace(day=min(day, _last_day(first_of_month)))
