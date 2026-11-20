"""The monthly report: one month's money in, money out and what changed, all computed here.

Pure: it reads a ledger context and returns the figures and the sentences that carry them. The
sentences are templates filled in by code (ARCHITECTURE.md §9: written text gets its numbers
through placeholders), so no model is involved and no figure can drift from the ledger.
"""

from __future__ import annotations

import re
from typing import Any

from pocket_common.money import pct_half_up

from core_api.i18n import month_name, t
from core_api.ledger import mathx, summary
from core_api.ledger.context import Ctx

MONTH_KEY = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")
MONTHS_OFFERED = 6


def _label(ctx: Ctx, key: str, with_year: bool = True) -> str:
    year, month = key.split("-")
    name = month_name(ctx.lang, int(month))
    return f"{name} {year}" if with_year else name


def months_with_data(ctx: Ctx) -> list[str]:
    """Complete months that have any transaction, newest first."""
    seen = {x.budget_month for x in ctx.txns}
    out = []
    for back in range(1, 25):
        key = mathx.shift_month_key(ctx.month, -back)
        if key in seen:
            out.append(key)
        if len(out) == MONTHS_OFFERED:
            break
    return out


def monthly_report(ctx: Ctx, month: str | None = None) -> dict[str, Any]:
    """The report for `month` (YYYY-MM). Default: the latest complete month."""
    offered = months_with_data(ctx)
    key = month or (offered[0] if offered else mathx.shift_month_key(ctx.month, -1))
    if not MONTH_KEY.match(key):
        raise ValueError(f"not a month: {key}")
    prev = mathx.shift_month_key(key, -1)
    has_prev = any(x.budget_month == prev for x in ctx.txns)

    income = summary.income_in_month(ctx, key)
    spend = max(0, summary.expense_in_month(ctx, key))
    committed = max(0, summary.expense_in_month(ctx, key, "committed"))
    flexible = max(0, spend - committed)
    saved = sum(x.amount_paise for x in ctx.txns if x.budget_month == key and x.spend_class == "saving" and x.direction == "debit")
    net = income - spend - saved
    prev_spend = max(0, summary.expense_in_month(ctx, prev)) if has_prev else 0
    delta = spend - prev_spend
    categories = summary._category_rows(ctx, summary.category_totals(ctx, key))[:8]

    def M(paise: int) -> dict[str, Any]:  # noqa: N802 - the Money object, as elsewhere in the ledger
        return summary.M(ctx, paise)

    names = {"month": _label(ctx, key, with_year=False), "prev": _label(ctx, prev, with_year=False)}
    if not has_prev:
        spent_line = t(ctx.lang, "report.spent.first", spend=M(spend)["display"], **names)
    elif delta == 0:
        spent_line = t(ctx.lang, "report.spent.same", spend=M(spend)["display"], **names)
    else:
        spent_line = t(ctx.lang, "report.spent.less" if delta < 0 else "report.spent.more",
                       spend=M(spend)["display"], delta=M(abs(delta))["display"], **names)
    lines = [spent_line]
    if income > 0:
        lines.append(t(ctx.lang, "report.kept" if net >= 0 else "report.short", net=M(abs(net))["display"]))
    if categories:
        lines.append(t(ctx.lang, "report.top", category=categories[0]["name"]))

    return {
        "month": key, "month_label": _label(ctx, key), "previous_month": prev, "previous_label": _label(ctx, prev, with_year=False),
        "has_previous": has_prev,
        "income": M(income), "spend": M(spend), "committed": M(committed), "flexible": M(flexible), "saved": M(saved),
        "net": M(net), "net_abs": M(abs(net)), "net_is_positive": net >= 0,
        "previous_spend": M(prev_spend), "spend_delta": M(abs(delta)),
        "spend_direction": "same" if delta == 0 or not has_prev else ("down" if delta < 0 else "up"),
        "spend_delta_pct": pct_half_up(abs(delta), prev_spend) if has_prev and prev_spend > 0 else None,
        # shares of income, for the bar on the screen (whole per cent, computed here)
        "spend_pct_of_income": min(100, pct_half_up(spend, income)) if income > 0 else None,
        "saved_pct_of_income": min(100, pct_half_up(saved, income)) if income > 0 else None,
        # bar lengths for "this month against the last one", longest = 100
        "bars": {"month": pct_half_up(spend, max(spend, prev_spend)), "previous": pct_half_up(prev_spend, max(spend, prev_spend))},
        "categories": categories, "lines": lines,
        "months": [{"month": k, "label": _label(ctx, k, with_year=False)} for k in offered],
    }
