"""The monthly report: the figures add up, and every figure in a sentence is one the report computed."""

import re

import pytest
from core_api.ledger import mathx, summary
from core_api.ledger.context import Ctx
from core_api.reports.monthly import monthly_report, months_with_data
from core_api.seed.offline import Dataset

RUPEES = re.compile(r"-?₹[\d,]+(?:\.\d+)?(?: (?:lakh|crore|लाख|करोड़|லட்சம்|கோடி))?")


@pytest.fixture(scope="module")
def people() -> dict[str, Ctx]:
    return {str(row["persona_id"]): ctx for row, ctx in Dataset("demo").contexts()}


@pytest.mark.parametrize("persona", ["student", "first_job", "family", "gig", "shop", "investor"])
def test_the_figures_add_up(people: dict[str, Ctx], persona: str) -> None:
    ctx = people[persona]
    r = monthly_report(ctx)
    assert r["month"] == mathx.shift_month_key(ctx.month, -1) == "2026-10"
    income, spend, saved, net = (r[k]["paise"] for k in ("income", "spend", "saved", "net"))
    assert net == income - spend - saved
    assert r["net_is_positive"] == (net >= 0)
    assert r["committed"]["paise"] + r["flexible"]["paise"] == spend
    assert spend == max(0, summary.expense_in_month(ctx, "2026-10"))

    previous = r["previous_spend"]["paise"]
    assert r["spend_delta"]["paise"] == abs(spend - previous)
    assert r["spend_direction"] == ("down" if spend < previous else "up" if spend > previous else "same")
    assert r["net_abs"]["paise"] == abs(net)
    assert max(r["bars"].values()) == (100 if max(spend, previous) else 0) and min(r["bars"].values()) >= 0
    assert sum(c["amount"]["paise"] for c in r["categories"]) <= spend
    assert all(0 <= c["pct"] <= 100 for c in r["categories"])
    assert [c["amount"]["paise"] for c in r["categories"]] == sorted((c["amount"]["paise"] for c in r["categories"]), reverse=True)


@pytest.mark.parametrize("lang", ["en", "hi", "ta"])
def test_every_figure_in_a_sentence_comes_from_the_report(people: dict[str, Ctx], lang: str) -> None:
    for ctx in people.values():
        ctx.lang = lang
        r = monthly_report(ctx)
        shown = {r[k]["display"] for k in ("income", "spend", "saved", "net", "previous_spend", "spend_delta")}
        shown |= {r["net"]["display"].lstrip("-")}
        assert 2 <= len(r["lines"]) <= 3
        for line in r["lines"]:
            assert "{" not in line and "}" not in line, line
            for figure in RUPEES.findall(line):
                assert figure in shown, (figure, line)
        ctx.lang = ctx.user.language


def test_months_offered_are_complete_months_newest_first(people: dict[str, Ctx]) -> None:
    ctx = people["first_job"]
    offered = months_with_data(ctx)
    assert offered[0] == "2026-10" and len(offered) == 6
    assert offered == sorted(offered, reverse=True)
    assert ctx.month not in offered  # the month in progress is not a report
    r = monthly_report(ctx, "2026-08")
    assert (r["month"], r["previous_month"], r["month_label"]) == ("2026-08", "2026-07", "August 2026")
    assert [m["month"] for m in r["months"]] == offered


def test_the_first_month_has_nothing_to_compare_with(people: dict[str, Ctx]) -> None:
    ctx = people["first_job"]
    first = min(x.budget_month for x in ctx.txns)
    r = monthly_report(ctx, first)
    assert r["has_previous"] is False and r["spend_direction"] == "same" and r["spend_delta_pct"] is None
    assert r["previous_spend"]["paise"] == 0


def test_a_bad_month_is_refused(people: dict[str, Ctx]) -> None:
    for bad in ("2026-13", "october", "2026-1", "26-10"):
        with pytest.raises(ValueError):
            monthly_report(people["first_job"], bad)
